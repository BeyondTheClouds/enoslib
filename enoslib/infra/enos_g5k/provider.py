from collections import defaultdict
import copy
from contextlib import contextmanager
from datetime import datetime, time, timezone
import logging
import operator
import re
import pytz
from itertools import groupby
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    MutableMapping,
    Optional,
    Tuple,
    Union,
    cast,
)


from enoslib.api import run, CommandResult, CustomCommandResult
from enoslib.infra.enos_g5k.concrete import (
    ConcreteClusterConf,
    ConcreteGroup,
    ConcreteServersConf,
)
from .configuration import (
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
    get_api_client,
    get_api_username,
    get_clusters_status,
    _test_slot,
)
from enoslib.infra.enos_g5k.objects import (
    G5kHost,
    G5kNetwork,
    G5kProdNetwork,
    G5kSubnetNetwork,
    G5kVlanNetwork,
)
from enoslib.errors import (
    InvalidReservationCritical,
    InvalidReservationTime,
    InvalidReservationTooOld,
    NegativeWalltime,
)
from enoslib.infra.provider import Provider
from enoslib.infra.providers import Providers

from enoslib.infra.utils import mk_pools, pick_things
from enoslib.objects import Host, Networks, Roles
from enoslib.log import getLogger
from sshtunnel import SSHTunnelForwarder

from grid5000.exceptions import Grid5000CreateError


logger = getLogger(__name__, ["G5k"])


def _check_deployed_nodes(
    net: G5kNetwork, fqdns: List[str]
) -> Tuple[List[str], List[str]]:
    """This is borrowed from execo."""
    # we translate in the right vlan
    nodes = [t[1] for t in net.translate(fqdns)]
    # we build a one-off list of hosts to run the check command
    hosts = [Host(n, user="root") for n in nodes]
    deployed = []
    undeployed = []
    cmd = "! (mount | grep -E '^/dev/[[:alpha:]]+2 on / ')"

    deployed_results = run(
        cmd,
        roles=hosts,
        raw=True,
        gather_facts=False,
        task_name="Check deployment",
        # Make sure we don't wait too long
        extra_vars=dict(ansible_timeout=10),
        # Errors are expected
        # e.g the first time all hosts are unreachable
        on_error_continue=True,
    )
    for r in deployed_results.filter(task="Check deployment"):
        if r.ok():
            deployed.append(r.host)
        else:
            undeployed.append(r.host)

    # un-translate to stay in the fqdns world
    deployed = [t[1] for t in net.translate(deployed, reverse=True)]
    undeployed = [t[1] for t in net.translate(undeployed, reverse=True)]

    return deployed, undeployed


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
                logger.debug(
                    "The impossible happened: an explicitly requested "
                    "server is missing in the concrete resource"
                )
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
            logger.error("Missing Network: are you reloading the right job ?")
            raise MissingNetworkError(site, n_type)
        if g5k_network is None:
            logger.error("Missing Network: are you reloading the right job ?")
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


class G5kTunnel:
    """A class to initiate a tunnel to a targetted service inside Grid'5000.

    Can be used as a context manager (will close the tunnel automatically).
    Note that this is a noop when called from inside Grid'5000.

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
        """Start the tunnel.

        Returns:
            A tuple composed of the local address , the local port and the
            tunnel object (if any)
        """
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


def check() -> List[Tuple[str, bool, str]]:
    # first check ssh to access.grid5000.fr
    statuses = []
    user = None

    try:
        # Get the username
        # This might be empty and valid when running from a frontend
        user = get_api_username()
    except Exception as e:
        statuses.append(("api:conf", False, str(e)))
        # no need to continue
        return statuses

    access = Host("access.grid5000.fr", user=get_api_username())
    # beware: on access the homedir isn't writable (so using raw)
    r = run(
        "hostname",
        access,
        raw=True,
        on_error_continue=True,
        task_name=f"Connecting to {user}@{access.alias}",
    )
    if isinstance(r[0], CommandResult):
        statuses.append(
            (
                "ssh:access",
                r[0].rc == 0,
                r[0].stderr if r[0].rc != 0 else f"Connection to {access.alias}",
            )
        )
    elif isinstance(r[0], CustomCommandResult):
        # hostname don't fail so if we get an error at this point
        # it's because of the connection
        # The result in this case is a CustomCommandResult
        # see:
        # CustomCommandResult(host='acces.grid5000.fr', task='Connecting to
        # msimonin@acces.grid5000.fr', status='UNREACHABLE',
        # payload={'unreachable': True, 'msg': 'Failed to connect to the host
        # via ssh: channel 0: open failed: administratively prohibited: open
        # failed\r\nstdio forwarding failed\r\nssh_exchange_identification:
        # Connection closed by remote host', 'changed': False})
        statuses.append(("ssh:access", False, r[0].payload["msg"]))
        # no need to continue if that's failing
        return statuses
    else:
        raise ValueError("Impossible command result type received, this is a bug")

    one_frontend = Host("rennes.grid5000.fr", user=get_api_username())
    r = run(
        "hostname",
        access,
        raw=True,
        on_error_continue=True,
        task_name=f"Connecting to {user}@{access.alias}",
    )
    if r[0].rc == 0:
        statuses.append(("ssh:access:frontend", True, f"Connection {one_frontend}"))
    else:
        # see above
        statuses.append(("ssh:access:frontend", False, r[0].payload["msg"]))

    try:
        gk = get_api_client()
        _ = gk.sites.list()
    except Exception as e:
        statuses.append(("api:access", False, str(e)))
        return statuses

    # all clear
    statuses.append(("api:access", True, ""))

    return statuses


class G5kBase(Provider):
    """(internal)Provider dedicated to single site interaction."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # make sure we are dealing with a single site
        self.driver = get_driver(self.provider_conf)
        # will hold the concrete version of the hosts
        self.hosts = []
        # will hold the concrete version of the networks
        self.networks = []
        # will hold the concrete hosts deployed/undeployed after calling (ka)deploy3
        self.deployed = []
        self.undeployed = []

        # will hold the hosts reachable through ssh
        # - if no deployment has been performed, this will be self.hosts
        # - if a deployment has been performed, this will be self.deployed
        self.sshable_hosts = []

        # will hold the status of the cluster
        self.clusters_status = None

        # execo connection params for routines configuration and checks
        # the priv key path is built from the public key path by removing the
        # .pub suffix...
        self.key_path = self.provider_conf.key
        priv_key = self.key_path.replace(".pub", "")
        self.root_conn_params = {"user": "root", "keyfile": priv_key}

    def init(
        self, force_deploy: bool = False, start_time: Optional[int] = None, **kwargs
    ):
        """Take ownership over some Grid'5000 resources (compute and networks).

        The function does the heavy lifting of transforming your
        abstract resource configuration into concrete resources.

        From a high level perspective it works as follow:

        - First it transforms the configuration of resources into an actual
          OAR resource selection string (one single reservation per provider
          instance).
        - It requests the API to get the corresponding resources (job and
          optionally deploys a environment)
        - Those resources are then mapped back to every single item on the
          configuration.
        - Finally it applies some more operations (set nodes on vlans,
          configure secondary interfaces) before returning.

        .. note::

            The call to the function is **idempotent** and the following is ensured:

            - Existing job(s) (based on the name) will be reloaded - The
              mapping between concrete resources and their corresponding roles
              is fixed across runs. This includes:
                - the mapping between machines and roles
                - the mapping between networks and roles
                - the mapping between network cards and networks
            - Deployments is performed only on nodes that are not deployed yet
              (up to three attempts).
            - At the end machine are reachable using the root account.

        Args:
            force_deploy: bool
                True iff the environment must be redeployed
            start_time: timestamp (int in seconds)
                Time at which to start the job, by default whenever
                possible

        Raises:
            MissingNetworkError:
                If one network is missing in comparison to what is claimed.
            NotEnoughNodesError:
                If the `min` constraints can't be met.
            InvalidReservationTime:
                If the set reservation_date from provider.conf isn't free
            InvalidReservationOld:
                If the set reservation_date from provider.conf is in the past
            InvalidReservationCritical:
                Any other error that might occur during the reservation is deemed
                critical

        Returns:
            Two dictionaries (roles, networks) representing the inventory of
            resources.
        """
        _force_deploy = self.provider_conf.force_deploy
        self.provider_conf.force_deploy = _force_deploy or force_deploy
        if start_time:
            self.set_reservation(start_time)
        self.networks = []
        self.hosts = []
        self.launch()

        return self._to_enoslib()

    def ensure_reserved(self):
        self.reserve()

    def destroy(self, wait=False):
        """Destroys the jobs."""
        self.driver.destroy(wait=wait)

    @property
    def jobs(self):
        return self.driver.get_jobs()

    def launch(self):
        self.reserve()
        self.wait()

        oar_nodes, oar_networks = self.driver.resources()
        machines = _concretize_nodes(self.provider_conf.machines, oar_nodes)
        self.networks = _concretize_networks(self.provider_conf.networks, oar_networks)
        self.hosts = _join(machines, self.networks)

        # trigger necessary side effects on the API for instance
        for h in self.hosts:
            h.mirror_state()

        self.sshable_hosts = self.hosts

        if JOB_TYPE_DEPLOY in self.provider_conf.job_type:
            self.deploy()
            self.dhcp_networks()
        else:
            # TODO: let user opt out of this
            # even if they won't do much with enoslib in this case.
            self.grant_root_access()

    @staticmethod
    def timezone():
        return pytz.timezone("Europe/Paris")

    def reserve(self):
        try:
            # this is async (will keep the info of the jobs)
            self.driver.reserve()
        except Grid5000CreateError as error:
            # OAR is kind enough to provide an estimate for a possible start time.
            # we capture this start time (if it exists in the error) to forge a special
            # error. This error is used for example in a multi-providers setting
            # to update the search window of the common slot.
            search = re.search(
                r"Reservation not valid --> KO \(This reservation could run at (\d{4}-"
                r"\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)",
                format(error),
            )
            if search is not None:
                date = datetime.strptime(search.group(1), "%Y-%m-%d %H:%M:%S")
                date = self.timezone().localize(date)
                raise InvalidReservationTime(date)
            search = re.search(
                "Reservation too old",
                format(error),
            )
            if search is not None:
                raise InvalidReservationTooOld()
            else:
                raise InvalidReservationCritical(format(error))

    def async_init(self, start_time: Optional[int] = None, **kwargs):
        """Reserve but don't wait.

        No node/network information can't be retrieved at this moment.
        If a start_time is provided, set the reservation date to it.
        """
        if start_time:
            self.set_reservation(start_time)
        self.reserve()

    def wait(self):
        self.driver.wait()

    def deploy(self) -> Tuple[List[G5kHost], List[G5kNetwork]]:
        def _key(host):
            """Get the site and the primary network of a concrete description"""
            site, _, _ = host._where
            return site, host.primary_network

        # Should we deploy whatever the previous state ?
        force_deploy = self.provider_conf.force_deploy

        # G5k api requires to create one deployment per site and per
        # network type.
        # hosts = copy.deepcopy(self.hosts)
        hosts = self.hosts
        s_hosts = sorted(hosts, key=_key)
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
            deployed: List[str] = []
            undeployed: List[str] = fqdns
            if not force_deploy:
                deployed, undeployed = _check_deployed_nodes(net, fqdns)

            if force_deploy or not deployed:
                deployed, undeployed = self.driver.deploy(site, undeployed, options)

            if undeployed:
                logger.warning(f"Undeployed nodes: {undeployed}")

            # set the ssh_address attribute of the concrete hosts
            for fqdn, t_fqdn in net.translate(fqdns):
                # get the corresponding host
                h = [host for host in hosts if host.fqdn == fqdn][0]
                h.ssh_address = t_fqdn
            self.deployed = [h for h in _hosts if h.fqdn in deployed]
            self.undeployed = [h for h in _hosts if h.fqdn in undeployed]
            self.sshable_hosts = self.deployed
        return self.deployed, self.undeployed

    def dhcp_networks(self):
        dhcp = self.provider_conf.dhcp
        if dhcp:
            logger.debug("Configuring network interfaces on the nodes")
            hosts = [
                Host(
                    h.ssh_address,
                    user="root",
                    extra=dict(cmd=h.dhcp_networks_command()),
                )
                for h in self.sshable_hosts
            ]
            # cmd might be empty
            run("echo '' ; {{ cmd }}", hosts, task_name="Run dhcp on the nodes")

    def grant_root_access(self):
        hosts = [
            Host(
                h.ssh_address,
                user=self.driver.get_user(),
                extra=dict(cmd=h.grant_root_access_command()),
            )
            for h in self.sshable_hosts
        ]
        run(
            "{{ cmd }}", hosts, task_name="Granting root access on the nodes (sudo-g5k)"
        )

    def _to_enoslib(self):
        """Transform from provider specific resources to framework resources."""
        # index the host by their associated roles
        hosts = Roles()
        # used to de-duplicate host objects in the roles datastructure
        _hosts = []
        for host in self.sshable_hosts:
            h = Host(host.ssh_address, user="root")
            if h in _hosts:
                h = _hosts[_hosts.index(h)]
            else:
                _hosts.append(h)
            hosts.add_one(h, host.roles)

        # doing the same on networks
        networks = Networks()
        _networks = []
        for network in self.networks:
            roles, enos_networks = network.to_enos()
            for enos_network in enos_networks:
                if enos_network in _networks:
                    net = _networks[_networks.index(enos_network)]
                else:
                    net = enos_network
                    _networks.append(net)
                networks.add_one(net, roles)
        return hosts, networks

    @staticmethod
    def tunnel(address: str, port: int):
        """Create a tunnel if necessary between here and there (in G5k).

        Args:
            address: str
                The remote address to reach (assuming inside g5k)
            port: int
                The remote port to reach

        Returns
            The context manager
        """
        return G5kTunnel(address, port).start()

    @contextmanager
    def firewall(
        self,
        hosts: Iterable[Host] = None,
        port: Optional[Union[int, List[int]]] = None,
        src_addr: Optional[Union[str, List[str]]] = None,
        proto: str = "tcp+udp",
    ):
        """Context manager to manage firewall rules

        - Create a firewall opening when entering
        - Delete the firewall opening when exiting

        Args:
            hosts:
                limit the rule to a set of hosts.
                if None, rules will be applied on all hosts of all underlying jobs.
            port:
                ports to open
            src_addr:
                source addresses to consider
            proto:
                protocol to consider
        """
        self.fw_create(hosts=hosts, port=port, src_addr=src_addr, proto=proto)
        try:
            yield
        except Exception as e:
            raise e
        finally:
            self.fw_delete()

    def fw_delete(self):
        """Delete all existing rules."""
        jobs = self.driver.get_jobs()
        for job in jobs:
            logger.info(f"Removing firewall rules for job({job.uid})")
            job.firewall.delete()

    def fw_create(
        self,
        hosts: Iterable[Host] = None,
        port: Optional[Union[int, List[int]]] = None,
        src_addr: Optional[Union[str, List[str]]] = None,
        proto: str = "tcp+udp",
    ):
        """Create a firewall rules

        Reference: https://www.grid5000.fr/w/Reconfigurable_Firewall

        Note that ``port`` and ``src_addr`` and ``proto`` are passed to the API
        calls without any change. It means that accepted values are those
        accepted by the REST API.

        Args:
            hosts:
                limit the rule to a set of hosts.
                if None, rules will be applied on all hosts of all underlying jobs.
            port:
                ports to open
            src_addr:
                source addresses to consider
            proto:
                protocol to consider
        """

        def to_ipv6_dests(hosts: Iterable[str]):
            """util function to build the ipv6node string."""
            dests = []
            for dest in hosts:
                _dest = dest.split(".")
                _dest = [f"{_dest[0]}-ipv6"] + _dest[1:]
                dests.append(".".join(_dest))
            return dests

        jobs = self.driver.get_jobs()

        data: Dict[str, Any] = {}
        data.update(proto=proto)
        if port is not None:
            # cannot give port if proto == all"
            data.update(port=port)
        if src_addr is not None:
            # src_addr is optional
            data.update(src_addr=src_addr)

        for job in jobs:
            # build the destinations to consider
            # that either the set of all the nodes of the jobs
            # or only the one corresponding to the hosts passed
            assigned_hosts = job.assigned_nodes
            if hosts is not None:
                limit_hosts = [h.alias for h in hosts]
            else:
                limit_hosts = assigned_hosts
            # restrict the list of addr to consider
            # this is supposed to be a neutral operation if
            # hosts=None
            addrs = to_ipv6_dests(set(assigned_hosts).intersection(limit_hosts))
            data.update(addr=addrs)
            logger.info(f"Creating firewall rules {data}")
            job.firewall.create([data])

    def test_slot(self, start_time: int, end_time: int) -> bool:
        """Test if it is possible to reserve the configuration corresponding
        to this provider at start_time"""
        demands: MutableMapping[str, int] = defaultdict(int)
        exact_nodes = defaultdict(list)
        for machine in self.provider_conf.machines:
            cluster = machine.cluster
            number, exact = machine.get_demands()
            demands[cluster] += number
            exact_nodes[cluster].extend(exact)

        if self.clusters_status is None:
            self.clusters_status = get_clusters_status(demands.keys())

        return _test_slot(
            start_time,
            self.provider_conf.walltime,
            self.provider_conf.machines,
            self.clusters_status,
        )

    def set_reservation(self, timestamp: int):
        date = datetime.fromtimestamp(timestamp, timezone.utc)
        date = date.astimezone(tz=self.timezone())
        self.provider_conf.reservation = date.strftime("%Y-%m-%d %H:%M:%S")
        self.driver.reservation_date = self.provider_conf.reservation

    def offset_walltime(self, offset: int):
        walltime_part = self.provider_conf.walltime.split(":")
        walltime_sec = (
            int(walltime_part[0]) * 3600
            + int(walltime_part[1]) * 60
            + int(walltime_part[2])
            + offset
        )
        if walltime_sec <= 0:
            raise NegativeWalltime
        new_walltime = time(
            hour=int(walltime_sec / 3600),
            minute=int((walltime_sec % 3600) / 60),
            second=int(walltime_sec % 60),
        )

        self.provider_conf.walltime = new_walltime.strftime("%H:%M:%S")

    def is_created(self):
        return not (not self.driver.get_jobs())


class G5k(G5kBase):
    """The provider to use when interacting with Grid'5000.

    Most of the methods are inherited
    from :py:class:`~enoslib.infra.enos_g5k.provider.G5kBase`.
    """

    def reserve(self):
        """Reserve the resources described in the configuration

        This support multisite configuration.
        """
        sites = self.provider_conf.sites

        if len(sites) == 1:
            # follow the super behaviour
            # which is scoped to one single site anyway.
            super().reserve()
        else:
            # Use a temporary Providers instance to secure the resources.  Self
            # being scoped to several sites the set of reserved resources will
            # be reloaded by the current class in the subsequent steps event if
            # they have been reserved by the temporary Providers instance.
            confs_per_site = [self.provider_conf.restrict_to(site) for site in sites]
            providers = Providers([G5kBase(conf) for conf in confs_per_site])
            providers.async_init()


def _lookup_networks(network_id: str, networks: List[G5kNetwork]):
    """What is the concrete network corresponding the network declared in the conf.

    We'll need to review that, later.
    """
    match = [net for net in networks if net.id == network_id]
    # if it has been validated the following is valid
    return match[0]
