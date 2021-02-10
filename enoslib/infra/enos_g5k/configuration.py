from enoslib.infra.enos_g5k.g5k_api_utils import get_cluster_site
from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_ENV_NAME,
    DEFAULT_JOB_NAME,
    DEFAULT_JOB_TYPE,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_WALLTIME,
    DEFAULT_SSH_KEYFILE,
    KAVLAN_TYPE,
    SUBNET_TYPES,
)
from .schema import SCHEMA, G5kValidator


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.dhcp = True
        self.force_deploy = False
        self.env_name = DEFAULT_ENV_NAME
        self.job_name = DEFAULT_JOB_NAME
        # since https://gitlab.inria.fr/discovery/enoslib/-/issues/103
        # we need to be able to pass ["allow_classic_ssh", "exotic"]
        # so we wrap this in an array. This is also a chance to align this with
        # the G5k api which requires an array.
        # At some point we'll need to rename this to job_type*s*
        self.job_type = [DEFAULT_JOB_TYPE]
        self.key = DEFAULT_SSH_KEYFILE
        self.oargrid_jobids = None
        self.project = None
        self.queue = DEFAULT_QUEUE
        self.reservation = None
        self.walltime = DEFAULT_WALLTIME

        self._machine_cls = GroupConfiguration
        self._network_cls = NetworkConfiguration

    def add_machine(self, *args, **kwargs):
        # we need to discriminate between Cluster/Server
        if kwargs.get("servers") is not None:
            self.add_machine_conf(ServersConfiguration(*args, **kwargs))
        elif kwargs.get("cluster") is not None:
            self.add_machine_conf(ClusterConfiguration(*args, **kwargs))
        else:
            ValueError("Must be a cluster or server configuration")
        return self

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        if validate:
            G5kValidator.validate(dictionnary)

        self = cls()
        # populating the attributes
        for k in self.__dict__.keys():
            v = dictionnary.get(k)
            if v is not None:
                setattr(self, k, v)
        if isinstance(self.job_type, str):
            self.job_type = [self.job_type]

        _resources = dictionnary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.networks = [NetworkConfiguration.from_dictionnary(n) for n in _networks]
        self.machines = [
            GroupConfiguration.from_dictionnary(m, self.networks) for m in _machines
        ]

        self.finalize()
        return self

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


class GroupConfiguration:
    """Base class for a group of machine."""

    def __init__(
        self,
        *,
        roles=None,
        cluster=None,
        site=None,
        min=0,
        primary_network=None,
        secondary_networks=None,
    ):
        self.roles = roles
        self.cluster = cluster
        self.site = site
        # allow testing (pass a site name)
        if cluster is not None and site is None:
            self.site = self.site_of(self.cluster)
        self.min = min
        self.primary_network = primary_network
        self.secondary_networks = []
        if secondary_networks is not None:
            self.secondary_networks = secondary_networks

    def site_of(self, cluster: str):
        return get_cluster_site(cluster)

    def to_dict(self):
        d = {}
        d.update(
            roles=self.roles,
            primary_network=self.primary_network.id,
            secondary_networks=[n.id for n in self.secondary_networks],
        )
        return d

    @classmethod
    def from_dictionnary(cls, dictionnary, networks=None):
        if networks is None or networks == []:
            raise ValueError("At least one network must be set")

        roles = dictionnary["roles"]
        # cluster and servers are no individually optionnal
        # nevertheless the schema validates that at least one is set
        cluster = dictionnary.get("cluster")
        servers = dictionnary.get("servers")
        # check here if there's only one site and cluster in servers
        primary_network_id = dictionnary["primary_network"]

        secondary_networks_ids = dictionnary.get("secondary_networks", [])

        primary_network = [n for n in networks if n.id == primary_network_id]
        if len(primary_network) < 1:
            raise ValueError(
                "Primary network with id={id} not found".format(id=primary_network_id)
            )

        secondary_networks = [n for n in networks if n.id in secondary_networks_ids]
        if len(secondary_networks_ids) != len(secondary_networks):
            raise ValueError("Secondary network resolution fails")

        if servers is not None:
            return ServersConfiguration(
                roles=roles,
                servers=servers,
                primary_network=primary_network[0],
                secondary_networks=secondary_networks,
            )

        if cluster is not None:
            kwargs = {}
            nodes = dictionnary.get("nodes")
            if nodes is not None:
                kwargs.update(nodes=nodes)
            return ClusterConfiguration(
                roles=roles,
                cluster=cluster,
                primary_network=primary_network[0],
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
        print(d)
        return d

    def get_demands(self):
        return self.nodes, []

    def oar(self):
        if int(self.nodes) <= 0:
            return self.site, None
        criterion = "{cluster='%s'}/nodes=%s" % (self.cluster, self.nodes)
        return self.site, criterion


class ServersConfiguration(GroupConfiguration):
    def __init__(self, *, servers=None, **kwargs):

        super().__init__(**kwargs)
        if servers is None:
            raise ValueError("Servers can't be empty")

        # The intent of the below lines is to set the cluster attribute even if
        # only servers are set. Since network configuration are only
        # homogeneous at the cluster level, we can't have servers from
        # different cluster in a machine group description. Indeed there would
        # be a risk to fail at network configuration time (think about
        # secondary interfaces)

        def extract_site_cluster(s):
            r = s.split(".")
            c = r[0].split("-")
            return (c[0], r[1])

        cluster_site = set([extract_site_cluster(s) for s in servers])
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
        criterion = ["{network_address='%s'}/nodes=1" % s for s in self.servers]
        return self.site, "+".join(criterion)


class NetworkConfiguration:
    def __init__(self, *, id=None, roles=None, type=None, site=None):
        # NOTE(msimonin): mandatory keys will be captured by the finalize
        # function of the configuration.
        self.roles = roles
        self.id = id
        self.roles = roles
        self.type = type
        self.site = site

    @classmethod
    def from_dictionnary(cls, dictionnary):
        id = dictionnary["id"]
        type = dictionnary["type"]
        roles = dictionnary["roles"]
        site = dictionnary["site"]

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
