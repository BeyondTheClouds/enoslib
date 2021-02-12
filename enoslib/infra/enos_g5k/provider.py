# -*- coding: utf-8 -*-
from collections import defaultdict
import copy
import logging
import operator
from itertools import groupby
from typing import List, Optional, Tuple, cast

from sshtunnel import SSHTunnelForwarder

from enoslib.objects import Host
from enoslib.infra.enos_g5k.concrete import (
    ConcreteClusterConf,
    ConcreteGroup,
    ConcreteServersConf,
)
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    GroupConfiguration,
    NetworkConfiguration,
    ServersConfiguration,
)
from enoslib.infra.enos_g5k.constants import (
    JOB_TYPE_DEPLOY,
    KAVLAN_TYPE,
    PROD,
    PROD_VLAN_ID,
    SLASH_16,
    SLASH_22,
)
from enoslib.infra.enos_g5k.driver import get_driver
from enoslib.infra.enos_g5k.error import MissingNetworkError
from enoslib.infra.enos_g5k.g5k_api_utils import (
    OarNetwork,
    get_api_username,
    _do_synchronise_jobs,
)
from enoslib.infra.enos_g5k.objects import (
    G5kHost,
    G5kNetwork,
    G5kProdNetwork,
    G5kSubnetNetwork,
    G5kVlanNetwork,
)
from enoslib.infra.enos_g5k.remote import DEFAULT_CONN_PARAMS, get_execo_remote
from enoslib.infra.enos_g5k.utils import run_commands
from enoslib.infra.provider import Provider
from enoslib.infra.utils import mk_pools, pick_things

logger = logging.getLogger(__name__)


def _concretize_nodes(
    group_configs: List[GroupConfiguration], g5k_nodes: List[str]
) -> List[ConcreteGroup]:
    """Create a mapping between the configuration and the nodes given by OAR.

    The mapping *must* be fully deterministic.
    (whatever is the order of the oar nodes in the input list)
    Returned elements are internal object that will be combined later with
    concrete networks to forge convenient hosts object
    see py:func:`enoslib.infra.enos_g5k.utils.join`.

    Args:
        group_configs: list of group configuration.
        oar_nodes: create node names as returned by OAR

    Returns:
        The mapping between every single group_config and a corresponding oar nodes.:w
    """

    # we fulfill the specific servers demands
    _oar_nodes = copy.deepcopy(g5k_nodes)
    servers_config = [m for m in group_configs if isinstance(m, ServersConfiguration)]
    concrete: List[ConcreteGroup] = []
    for config in servers_config:
        # create a concrete version
        assert isinstance(config, ServersConfiguration)
        _concrete_servers = []
        for s in config.servers:
            # NOTE(msimonin) this will simply fails if the node isn't here
            try:
                _oar_nodes.remove(s)
                _concrete_servers.append(s)
            except ValueError:
                # The server is missing in the concrete version
                # this shouldn't happen because it has been explicitly requested
                pass
        c = ConcreteServersConf(_concrete_servers, config)
        c.raise_for_min()
        concrete.append(c)

    # now with the remaining nodes we try to fulfil the requirements at the
    # cluster level
    snodes = sorted(_oar_nodes, key=lambda n: n)
    pools_cluster = mk_pools(snodes, lambda n: n.split("-")[0])
    clusters_config = [m for m in group_configs if isinstance(m, ClusterConfiguration)]
    # We fulfill min requirements
    # Just considering machines with min value specified
    min_machines = sorted(clusters_config, key=operator.attrgetter("min"))
    # keep track of the concrete here because we'll need to feed them with the
    # remaining items
    concrete_clusters = []
    for cluster_config in min_machines:
        cluster_config = cast(ClusterConfiguration, cluster_config)
        cluster = cluster_config.cluster
        nb = cluster_config.min
        _concrete_servers = pick_things(pools_cluster, cluster, nb)
        ccc = ConcreteClusterConf(_concrete_servers, cluster_config)
        ccc.raise_for_min()
        concrete.append(ccc)
        concrete_clusters.append(ccc)

    # We then fill the remaining without
    # If no enough nodes are there we silently continue
    for _concrete in concrete_clusters:
        cc = cast(ClusterConfiguration, _concrete.config)
        cluster = cc.cluster
        nb = cc.nodes - len(_concrete.oar_nodes)
        c_nodes = pick_things(pools_cluster, cluster, nb)
        #  put concrete hostnames here
        _concrete.oar_nodes.extend([c_node for c_node in c_nodes])

    return concrete


def _concretize_networks(
    network_configs: List[NetworkConfiguration], oar_networks: List[OarNetwork]
) -> List[G5kNetwork]:
    """Create a mapping between the network configuration and the networks given by OAR.

    The mapping *must* be fully deterministic.
    (whatever is the order of the oar networks in the input list)

    Args:
        group_configs: list of group configuration.
        oar_nodes: create node names as returned by OAR

    Returns:
        The mapping between every single group_config and a corresponding oar nodes.
    """
    # NOTE(msimonin): Sorting avoid non deterministic mapping
    # here we also sort by descriptor to differentiate between vlans
    s_api_networks = sorted(
        oar_networks, key=lambda n: (n.site, n.nature, n.descriptor)
    )
    pools = mk_pools(s_api_networks, lambda n: (n.site, n.nature))
    g5k_networks = []
    for network_config in network_configs:
        site = network_config.site
        n_type = network_config.type
        # roles and ids are important to keep as they are application specific
        roles = network_config.roles
        n_id = network_config.id
        # On grid'5000 a slash_16 is 64 slash_22
        # So if we ask for a slash_16 we return 64 sash_22
        # yes, this smells
        g5k_network: Optional[G5kNetwork] = None
        if n_type == SLASH_16:
            _networks = pick_things(pools, (site, SLASH_22), 64)
            if _networks != []:
                g5k_network = G5kSubnetNetwork(
                    roles, n_id, site, [n.descriptor for n in _networks]
                )
        elif n_type == SLASH_22:
            _networks = pick_things(pools, (site, n_type), 1)
            if _networks != []:
                g5k_network = G5kSubnetNetwork(
                    roles, n_id, site, [n.descriptor for n in _networks]
                )
        elif n_type == PROD:
            _networks = pick_things(pools, (site, n_type), 1)
            if _networks != []:
                g5k_network = G5kProdNetwork(roles, n_id, site)
        elif n_type in KAVLAN_TYPE:
            _networks = pick_things(pools, (site, n_type), 1)
            if _networks != []:
                g5k_network = G5kVlanNetwork(roles, n_id, site, _networks[0].descriptor)
        else:
            raise MissingNetworkError(site, n_type)
        # pick_thing is best-effort
        if g5k_network is None:
            raise MissingNetworkError(site, n_type)

        g5k_networks.append(g5k_network)
    return g5k_networks


def _join(machines: List[ConcreteGroup], networks: List[G5kNetwork]) -> List[G5kHost]:
    """Actually create a list of host."""
    hosts = []
    for concrete_machine in machines:
        roles = concrete_machine.config.roles
        network_id = concrete_machine.config.primary_network.id
        primary_network = _lookup_networks(network_id, networks)
        secondary_networks = []
        for s in concrete_machine.config.secondary_networks:
            secondary_networks.append(_lookup_networks(s.id, networks))
        for apinode in concrete_machine.oar_nodes:
            g5k_host = G5kHost(
                apinode,
                roles=roles,
                primary_network=primary_network,
                secondary_networks=secondary_networks,
            )
            hosts.append(g5k_host)
            # reference the host in the network (circular ref, use weakref if
            # that's an issue). My understanding is that this migh not be
            # necessary since the objects (hosts and networks) should have the
            # same lifetime
            primary_network.add_host(g5k_host)
            for s in secondary_networks:
                s.add_host(g5k_host)
    return hosts


class G5kTunnel(object):
    """A class to initiate a tunnel to a targetted service inside Grid'5000.

    Can be used as a context manager (will close the tunnel automatically).

    Args:
        address: The ip address/fqdn of the targetted service
        port: The port of the targetted service
    """

    def __init__(self, address: str, port: int):
        """"""
        self.address = address
        self.port = port

        # computed
        self.tunnel = None

    def start(self):
        """Start the tunnel."""
        import socket

        if "grid5000.fr" not in socket.getfqdn():
            logging.debug(f"Creating a tunnel to {self.address}:{self.port}")
            self.tunnel = SSHTunnelForwarder(
                "access.grid5000.fr",
                ssh_username=get_api_username(),
                remote_bind_address=(self.address, self.port),
            )
            self.tunnel.start()
            local_address, local_port = self.tunnel.local_bind_address
            return local_address, local_port, self.tunnel
        return self.address, self.port, None

    def close(self):
        """Close the tunnel.

        Note that this won't wait for any connection to finish first."""
        if self.tunnel is not None:
            logging.debug(f"Closing the tunnel to {self.address}:{self.port}")
            self.tunnel.stop(force=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()


def synchronise(*confs):
    """Find a suitable reservation date for all the confs passed."""

    def max_walltime(w1, w2):
        """lexicographic order on string XX:YY:ZZ

        string must be well-formed."""
        if w1 < w2:
            return w2
        else:
            return w1

    machines = []
    walltime = "00:00:00"
    for conf in confs:
        machines.extend(conf.machines)
        walltime = max(walltime, conf.walltime)

    return _do_synchronise_jobs(walltime, machines, force=True)


class G5k(Provider):
    """The provider to use when deploying on Grid'5000."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.driver = get_driver(self.provider_conf)
        # will hold the concrete version of the hosts
        self.hosts = []
        # will hold the concrete version of the networks
        self.networks = []
        self.deployed = []
        self.undeployed = []

        # execo connection params for routines configuration and checks
        # the priv key path is built from the public key path by removing the
        # .pub suffix...
        self.key_path = self.provider_conf.key
        priv_key = self.key_path.replace(".pub", "")
        self.root_conn_params = {"user": "root", "keyfile": priv_key}

    def init(self, force_deploy: bool = False):
        """Take ownership over some Grid'5000 resources (compute and networks).

        The function does the heavy lifting of transforming your
        abstract resource configuration into concrete resources.

        From a high level perspective it works as follow:

        - First it transforms the configuration of resources into an actual
          OAR resource selection string (one single reservation per provider
          instance).
        - It requests the API to get the corresponding resources (job and
          optionaly deploys a environment)
        - Those resources are then mapped back to every single item on the
          configuration.
        - Finally it applies some more operations (set nodes on vlans,
          configure secondary interfaces) before returning.

        .. note::

            The call to the function is **idempotent** and the following is ensured:

            - Existing job(s) (based on the name) will be reloaded - The
              mapping between concrete resources and their corresponding roles
              is fixed accros runs. This includes:
                - the mapping between machines and roles
                - the mapping between networks and roles
                - the mapping between network cards and networks
            - Deployments is performed only on nodes that are not deployed yet
              (up to three attempts).
            - At the end machine are reachable using the root account.

        Args:
            force_deploy (bool): True iff the environment must be redeployed
        Raises:
            MissingNetworkError: If one network is missing in comparison to
                what is claimed.
            NotEnoughNodesError: If the `min` constraints can't be met.

        Returns:
            Two dictionnaries (roles, networks) representing the inventory of
            resources.
        """
        _force_deploy = self.provider_conf.force_deploy
        self.provider_conf.force_deploy = _force_deploy or force_deploy
        self.launch()

        return self._to_enoslib()

    def destroy(self):
        """Destroys the jobs."""
        self.driver.destroy()

    def launch(self):
        # drop in replacement for Resource.launch
        self.reserve()
        if JOB_TYPE_DEPLOY in self.provider_conf.job_type:
            self.deploy()
            self.dhcp_networks()
        else:
            # TODO: let user opt out of this
            # even if they won't do much with enoslib in this case.
            self.grant_root_access()

    def reserve(self) -> List[G5kHost]:
        oar_nodes, oar_networks = self.driver.reserve(wait=True)
        machines = _concretize_nodes(self.provider_conf.machines, oar_nodes)
        self.networks = _concretize_networks(self.provider_conf.networks, oar_networks)
        self.hosts = _join(machines, self.networks)
        # trigger necessary side effects on the API for instance
        for h in self.hosts:
            h.mirror_state()
        return self.hosts

    def reserve_async(self):
        """Reserve but don't wait.

        No node/network information can't be retrieved at this moment.
        """
        self.driver.reserve(wait=False)

    def deploy(self):
        def _key(host):
            """Get the site and the primary network of a concrete description"""
            site, _, _ = host._where
            return site, host.primary_network

        # Should we deploy whatever the previous state ?
        force_deploy = self.provider_conf.force_deploy

        # G5k api requires to create one deployment per site and per
        # network type.
        s_hosts = sorted(self.hosts, key=_key)
        for (site, net), i_hosts in groupby(s_hosts, key=_key):
            _hosts = list(i_hosts)
            fqdns = [h.fqdn for h in _hosts]
            # handle deployment options
            # key option    config.update(environment=config.env_name)
            options = dict(
                environment=self.provider_conf.env_name, key=self.provider_conf.key
            )

            # We remove the vlan id for the production
            # network (it's undocumented behavior on G5k side) so let's not
            # take any risk of creating a black hole.
            if net.vlan_id and net.vlan_id != PROD_VLAN_ID:
                options.update(vlan=net.vlan_id)

            # Yes, this is sequential
            deployed, undeployed = [], fqdns
            if not force_deploy:
                deployed, undeployed = self._check_deployed_nodes(net, fqdns)

            if force_deploy or not deployed:
                deployed, undeployed = self.driver.deploy(site, undeployed, options)

            if undeployed:
                logger.warn(f"Undeployed nodes: {undeployed}")

            # set the ssh_address atrribute of the concrete hosts
            for fqdn, t_fqdn in net.translate(fqdns):
                # get the corresponding host
                h = [host for host in self.hosts if host.fqdn == fqdn][0]
                h.ssh_address = t_fqdn
            self.deployed = [h for h in _hosts if h.fqdn in deployed]
            self.undeployed = [h for h in _hosts if h.fqdn in undeployed]
        return self.deployed, self.undeployed

    def dhcp_networks(self):
        dhcp = self.provider_conf.dhcp
        if dhcp:
            logger.debug("Configuring network interfaces on the nodes")
            hosts_cmds = [
                (h.ssh_address, h.dhcp_networks_command()) for h in self.hosts
            ]
            run_commands(hosts_cmds, self.root_conn_params)

    def grant_root_access(self):
        user_conn_params = copy.deepcopy(self.root_conn_params)
        user_conn_params.update(user=self.driver.get_user())
        hosts_cmds = [
            (h.ssh_address, h.grant_root_access_command()) for h in self.hosts
        ]
        run_commands(hosts_cmds, user_conn_params)

    def _check_deployed_nodes(
        self, net: G5kNetwork, fqdns: List[str]
    ) -> Tuple[List[str], List[str]]:
        """This is borrowed from execo."""
        nodes = [t[1] for t in net.translate(fqdns)]
        deployed = []
        undeployed = []
        cmd = "! (mount | grep -E '^/dev/[[:alpha:]]+2 on / ')"

        deployed_check = get_execo_remote(cmd, nodes, DEFAULT_CONN_PARAMS)

        for p in deployed_check.processes:
            p.nolog_exit_code = True
            p.nolog_timeout = True
            p.nolog_error = True
            p.timeout = 10
        deployed_check.run()

        for p in deployed_check.processes:
            if p.ok:
                deployed.append(p.host.address)
            else:
                undeployed.append(p.host.address)

        # un-translate to stay in the fqdns world
        deployed = [t[1] for t in net.translate(deployed, reverse=True)]
        undeployed = [t[1] for t in net.translate(undeployed, reverse=True)]

        return deployed, undeployed

    def _to_enoslib(self):
        """Transform from provider specific resources to framework resources."""
        # index the host by their associated roles
        hosts = defaultdict(list)
        for host in self.hosts:
            for role in host.roles:
                h = Host(host.ssh_address, user="root")
                hosts[role].append(h)
        # doing the same on networks
        networks = defaultdict(list)
        for network in self.networks:
            roles, enos_networks = network.to_enos()
            for role in roles:
                networks[role].extend(enos_networks)
        return hosts, networks

    @staticmethod
    def tunnel(address: str, port: int):
        """Create a tunnel if necessary between here and there (in G5k).

        Args:
            address: The remote address to reach (assuming inside g5k)
            port: The remote port to reach

        Returns
            The context manager
        """
        return G5kTunnel(address, port).start()

    def __str__(self):
        return "G5k"


def _lookup_networks(network_id: str, networks: List[G5kNetwork]):
    """What is the concrete network corresponding the network declared in the conf.

    We'll need to review that, later.
    """
    match = [net for net in networks if net.id == network_id]
    # if it has been validated the following is valid
    return match[0]
