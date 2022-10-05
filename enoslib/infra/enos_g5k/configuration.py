from typing import List, Optional
from uuid import uuid4
import warnings

from enoslib.infra.enos_g5k.g5k_api_utils import get_cluster_site
from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_ENV_NAME_COMPAT,
    DEFAULT_JOB_NAME,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_WALLTIME,
    DEFAULT_SSH_KEYFILE,
    JOB_TYPE_DEPLOY,
    NETWORK_ROLE_PROD,
    KAVLAN_TYPE,
    SUBNET_TYPES,
)
from .schema import SCHEMA_USER, SCHEMA_INTERNAL, G5kValidator


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA_INTERNAL
    _VALIDATOR_FUNC = G5kValidator

    def __init__(self):
        super().__init__()
        self.dhcp = True
        self.force_deploy = False
        self.env_name: Optional[str] = None
        self.job_name = DEFAULT_JOB_NAME
        # since https://gitlab.inria.fr/discovery/enoslib/-/issues/103
        # this is an array.
        # At some point we'll need to rename this to job_type*s*
        self.job_type: List[str] = []
        self.key = DEFAULT_SSH_KEYFILE
        self.monitor = None
        self.oargrid_jobids = None
        self.project = None
        self.queue = DEFAULT_QUEUE
        self.reservation = None
        self.walltime = DEFAULT_WALLTIME

        self._machine_cls = GroupConfiguration
        self._network_cls = NetworkConfiguration

    def _set_default_primary_network(self, machine):
        """Auto-setup default (prod) network on a machine if missing."""
        if machine.primary_network is not None:
            return
        # Find existing network
        prod_nets = [
            net
            for net in self.networks
            if net.site == machine.site and net.type == "prod"
        ]
        if len(prod_nets) > 0:
            machine.primary_network = prod_nets[0]
        else:
            # Or create a new one
            net = NetworkConfiguration(
                id=f"prod-{machine.site}",
                type="prod",
                site=machine.site,
                roles=[NETWORK_ROLE_PROD],
            )
            self.add_network_conf(net)
            machine.primary_network = net

    def add_machine_conf(self, machine):
        # Add missing primary network if needed
        self._set_default_primary_network(machine)
        return super().add_machine_conf(machine)

    def add_machine(self, *args, **kwargs):
        # we need to discriminate between Cluster/Server
        if kwargs.get("servers") is not None:
            machine = ServersConfiguration(*args, **kwargs)
        elif kwargs.get("cluster") is not None:
            machine = ClusterConfiguration(*args, **kwargs)
        else:
            ValueError("Must be a cluster or server configuration")
        self.add_machine_conf(machine)
        return self

    @classmethod
    def from_dictionary(cls, dictionary, validate=True):
        if validate:
            cls.validate(dictionary, SCHEMA_USER)

        self = cls()
        # populating the attributes
        for k in self.__dict__.keys():
            v = dictionary.get(k)
            if v is not None:
                setattr(self, k, v)
        if isinstance(self.job_type, str):
            self.job_type = [self.job_type]

        _resources = dictionary["resources"]
        _machines = _resources["machines"]
        _networks = _resources.get("networks", [])
        self.networks = [NetworkConfiguration.from_dictionary(n) for n in _networks]
        self.machines = [
            GroupConfiguration.from_dictionary(m, self.networks) for m in _machines
        ]

        self.finalize()
        return self

    def finalize(self):
        # Fill in missing primary networks
        for machine in self.machines:
            self._set_default_primary_network(machine)
        # Deprecated parameters
        if "allow_classic_ssh" in self.job_type:
            warnings.warn(
                "'allow_classic_ssh' job type is deprecated, "
                "you can omit it to obtain the same behaviour.",
                DeprecationWarning,
            )
        # Kavlan needs deploy
        has_kavlan = False
        for net in self.networks:
            if net.type in KAVLAN_TYPE:
                has_kavlan = True
        if has_kavlan and JOB_TYPE_DEPLOY not in self.job_type:
            warnings.warn(
                "Kavlan networks require the use of 'deploy' job type, "
                "please update your code "
                "(automatically adding 'deploy' job type for compatibility).",
                DeprecationWarning,
            )
            self.job_type.append(JOB_TYPE_DEPLOY)
        if has_kavlan and not self.env_name:
            self.env_name = DEFAULT_ENV_NAME_COMPAT
            warnings.warn(
                "Kavlan networks require choosing an 'env_name' to deploy with, "
                "please update your code "
                f"(automatically selecting '{self.env_name}' for compatibility).",
                DeprecationWarning,
            )
        # Check parameters consistency
        if JOB_TYPE_DEPLOY in self.job_type and not self.env_name:
            raise ValueError("Parameter 'env_name' is required for 'deploy' job type")
        if self.env_name and JOB_TYPE_DEPLOY not in self.job_type:
            warnings.warn(
                "Parameter 'env_name' requires the use of 'deploy' job type, "
                "please update your code "
                "(automatically adding 'deploy' job type for compatibility).",
                DeprecationWarning,
            )
            self.job_type.append(JOB_TYPE_DEPLOY)
        # Call parent method that validates against the schema
        return super().finalize()

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in [
                "machines",
                "networks",
                "_machine_cls",
                "_network_cls",
            ]:
                continue
            d.update({k: v})

        d.update(
            resources={
                "machines": [m.to_dict() for m in self.machines],
                "networks": [n.to_dict() for n in self.networks],
            }
        )
        return d

    @property
    def sites(self) -> List[str]:
        """Get the exact sites in the configuration."""
        sites = [m.site for m in self.machines]
        sites += [m.site for m in self.networks]
        return list(set(sites))

    def restrict_to(self, site: str) -> "Configuration":
        import copy

        conf = copy.deepcopy(self)
        conf.machines = [m for m in self.machines if m.site == site]
        conf.networks = [n for n in self.networks if n.site == site]
        return conf


class GroupConfiguration:
    """Base class for a group of machine."""

    def __init__(
        self,
        *,
        roles=None,
        cluster=None,
        site=None,
        min=0,
        reservable_disks=False,
        primary_network=None,
        secondary_networks=None,
    ):
        self.roles = roles
        if self.roles is None:
            self.roles = []
        self.cluster = cluster
        self.site = site
        # allow testing (pass a site name)
        if cluster is not None and site is None:
            self.site = self.site_of(self.cluster)
        self.min = min
        self.reservable_disks = reservable_disks
        self.primary_network = primary_network
        self.secondary_networks = []
        if secondary_networks is not None:
            self.secondary_networks = secondary_networks

    def site_of(self, cluster: str):
        return get_cluster_site(cluster)

    def to_dict(self):
        d = {}
        primary_network_id = (
            self.primary_network.id if self.primary_network is not None else None
        )
        d.update(
            roles=self.roles,
            primary_network=primary_network_id,
            secondary_networks=[n.id for n in self.secondary_networks],
        )
        return d

    @classmethod
    def from_dictionnary(cls, *args, **kwargs):
        """Compatibility method (old method name that may still be used)"""
        warnings.warn(
            "from_dictionnary is deprecated in favor of from_dictionary",
            DeprecationWarning,
        )
        return cls.from_dictionary(*args, **kwargs)

    @classmethod
    def from_dictionary(cls, dictionary, networks=None):
        roles = dictionary["roles"]
        # cluster and servers are no individually optional
        # nevertheless the schema validates that at least one is set
        cluster = dictionary.get("cluster")
        servers = dictionary.get("servers")
        # check here if there's only one site and cluster in servers
        primary_network_id = dictionary.get("primary_network")

        secondary_networks_ids = dictionary.get("secondary_networks", [])

        primary_network = None
        if primary_network_id is not None:
            primary_networks = [n for n in networks if n.id == primary_network_id]
            if len(primary_networks) < 1:
                raise ValueError(
                    f"Primary network with id={primary_network_id} not found"
                )
            primary_network = primary_networks[0]

        secondary_networks = [n for n in networks if n.id in secondary_networks_ids]
        if len(secondary_networks_ids) != len(secondary_networks):
            raise ValueError("Secondary network resolution fails")

        if servers is not None:
            return ServersConfiguration(
                roles=roles,
                servers=servers,
                primary_network=primary_network,
                secondary_networks=secondary_networks,
            )

        if cluster is not None:
            kwargs = {}
            nodes = dictionary.get("nodes")
            if nodes is not None:
                kwargs.update(nodes=nodes)
            return ClusterConfiguration(
                roles=roles,
                cluster=cluster,
                primary_network=primary_network,
                secondary_networks=secondary_networks,
                **kwargs,
            )

        raise ValueError("Unable to build an instance MachineConfiguration")


class ClusterConfiguration(GroupConfiguration):
    def __init__(self, *, nodes=DEFAULT_NUMBER, **kwargs):
        super().__init__(**kwargs)
        self.nodes = nodes

    def to_dict(self):
        d = super().to_dict()
        d.update(cluster=self.cluster, nodes=self.nodes)
        return d

    def get_demands(self):
        return self.nodes, []

    def oar(self):
        if int(self.nodes) <= 0:
            return self.site, None
        disks = "(type='default' or type='disk') AND " if self.reservable_disks else ""
        criterion = f"{{{disks}cluster='{self.cluster}'}}/nodes={self.nodes}"
        return self.site, criterion


class ServersConfiguration(GroupConfiguration):
    def __init__(self, *, servers=None, **kwargs):

        super().__init__(**kwargs)
        if servers is None:
            raise ValueError("Servers can't be empty")

        # The intent of the below lines is to set the cluster attribute even if
        # only servers are set. Since network configuration are only
        # homogeneous at the cluster level, we can't have servers from
        # different cluster in a machine group description. Indeed, there would
        # be a risk to fail at network configuration time (think about
        # secondary interfaces)

        def extract_site_cluster(s):
            r = s.split(".")
            c = r[0].split("-")
            return (c[0], r[1])

        cluster_site = {extract_site_cluster(s) for s in servers}
        if len(cluster_site) > 1:
            raise ValueError(f"Several site/cluster for {servers}")

        # We force the corresponding cluster name
        self.cluster, self.site = cluster_site.pop()
        self.servers = servers

    def to_dict(self):
        d = super().to_dict()
        d.update(servers=self.servers)
        return d

    def get_demands(self):
        return len(self.servers), self.servers

    def oar(self):
        # that's a bit too defensive, we must have already checked that the
        # servers belong to the same cluster...
        if self.servers == []:
            return self.site, None
        disks = "(type='default' or type='disk') AND " if self.reservable_disks else ""
        server_list = ", ".join([f"'{s}'" for s in self.servers])
        nb_servers = len(self.servers)
        criterion = f"{{{disks}network_address in ({server_list})}}/nodes={nb_servers}"
        return self.site, criterion


class NetworkConfiguration:
    def __init__(self, *, id=None, roles=None, type=None, site=None):
        # NOTE(msimonin): mandatory keys will be captured by the finalize
        # function of the configuration.
        self.roles = roles
        if self.roles is None:
            self.roles = []
        self.type = type
        self.site = site
        self.id = id
        if id is None:
            self.id = str(uuid4())

    @classmethod
    def from_dictionnary(cls, *args, **kwargs):
        """Compatibility method (old method name that may still be used)"""
        warnings.warn(
            "from_dictionnary is deprecated in favor of from_dictionary",
            DeprecationWarning,
        )
        return cls.from_dictionary(*args, **kwargs)

    @classmethod
    def from_dictionary(cls, dictionary):
        id = dictionary["id"]
        type = dictionary["type"]
        roles = dictionary["roles"]
        site = dictionary["site"]

        return cls(id=id, roles=roles, type=type, site=site)

    def to_dict(self):
        d = {}
        d.update(id=self.id, type=self.type, roles=self.roles, site=self.site)
        return d

    def oar(self):
        site = self.site
        criterion = None
        if self.type in KAVLAN_TYPE:
            criterion = "{type='%s'}/vlan=1" % self.type
        if self.type in SUBNET_TYPES:
            criterion = "%s=1" % self.type
        return site, criterion
