from abc import ABC, abstractmethod

from netaddr.ip.sets import IPSet
from enoslib.infra.enos_g5k.constants import G5KMACPREFIX, KAVLAN_LOCAL_IDS

from grid5000.objects import VlanNodeManager
from netaddr.ip import IPAddress, IPNetwork
from enoslib.infra.enos_g5k.g5k_api_utils import (
    get_dns,
    get_node,
    get_subnet_gateway,
    get_vlan,
    get_vlans,
    set_nodes_vlan,
)
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from grid5000.base import RESTObject


class G5kNetwork(ABC):
    """Base abstract class for a network."""

    def __init__(self, roles: List[str], id: str, site: str):
        """Representation of an actual network in G5k

        Args:
            roles: roles/tags to give to this network (set by the application)
            id: the id to give to this network (set by the application)
            site: the site of this network
        """
        self.roles = roles
        self.id = id
        self.site = site
        # Lazy loading for some attribute
        # similar to self.__apinode for a host
        # it's intended to point the description in the API
        # Note that there is no entry for subnet in the API
        self._apinetwork: Optional[RESTObject] = None
        self._dns = None
        # circular references ahead
        self.hosts: List["G5kHost"] = []

    def __lt__(self, other):
        """In case you want to sort networks.

        This is used to sort/groupby host by network before deploying them.
        """
        if self.vlan_id is None:
            return True
        if other.vlan_id is None:
            return False
        return self.vlan_id < other.vlan_id

    @property
    def dns(self) -> Optional[str]:
        """Gets the DNS address for this network."""
        if self._dns is None:
            self._dns = get_dns(self.site)
        return self._dns

    @property
    @abstractmethod
    def apinetwork(self) -> Optional[RESTObject]:
        """Gets the underlying RESTObject representing the network.

        Only vlan and prod network have an equivalent entry in the API.
        None will be returned for subets.

        Returns:
            The corresponding RESTObject, None otherwise.
        """
        pass

    @property
    @abstractmethod
    def vlan_id(self) -> Optional[str]:
        """Get the vlan id.

        Return:
            The vlan id. None for subnets.
        """
        pass

    @property
    @abstractmethod
    def gateway(self) -> Optional[str]:
        """Get the gateway for this network.

        Returns:
            The gateway address as a string.
        """
        pass

    @property
    @abstractmethod
    def cidr(self) -> Optional[str]:
        """Get the network address in cid format.

        Returns:
            The cidre of the network. None for subnets.
        """
        pass

    @abstractmethod
    def translate(self, fqdns: List[str], reverse=True) -> Iterable[Tuple[str, str]]:
        """Gets the DNS names of the passed fqdns in this networks and vice versa.

        Args:
            fqdns: list of hostnames (host uid in the API) to translate.
            reverse: Do the opposite operation.

        Returns:
            List of translated names.
        """
        pass

    @abstractmethod
    def attach(self, fqdns: List[str], device: str):
        """Attach the specific devices into this network.

        Args:
            fqdns: list of hostnames (host uid in the API) to attach
            device: the NIC names to put on this network.
        """
        pass

    @abstractmethod
    def to_enos(self) -> List[Dict]:
        """Transform into an provider agnostic data structure.

        For legacy reason we're still using dicts here...

        Returns:
            a list of networks, each being a dict.
        """
        pass

    def add_host(self, host: "G5kHost"):
        """Add a host :py:class:`enoslib.infra.enos_g5k.objects.G5kHost`.

        Currently this doesn't attach the node.

        Args:
            host: The host to attach
        """
        self.hosts.append(host)

    def add_hosts(self, hosts: List["G5kHost"]):
        """Add some hosts :py:class:`enoslib.infra.enos_g5k.objects.G5kHost`.

        Currently this doesn't attach the node.

        Args:
            hosts: The list host to attach
        """

        # attach here ?
        self.hosts.extend(hosts)


class G5kVlanNetwork(G5kNetwork):
    def __init__(self, roles: List[str], id: str, site: str, vlan_id: str):
        """Representation of an actual Vlan in G5k.

        Args:
            roles: roles/tags to give to this network (set by the application)
            id: the id to give to this network (set by the application)
            site: the site of this network
            vlan_id: the vlan id of the vlan
        """
        super().__init__(roles, id, site)
        # forcing to string (the vlan_id of a prod network is DEFAULT)
        self._vlan_id = str(vlan_id)
        # the diff here with G5kHost is that we don't point to a resource of the API.
        self._info: Dict[str, str] = {}

    def _check_info(self):
        if not self._info:
            self._info = get_vlans(self.site)[self.vlan_id.lower()]

    def _check_apinetwork(self):
        if self._apinetwork is None:
            self._apinetwork = get_vlan(self.site, self.vlan_id)

    @property
    def vlan_id(self) -> Optional[str]:
        """Get a vlan id if any."""
        return self._vlan_id

    @property
    def cidr(self) -> str:
        self._check_info()
        return self._info["network"]

    @property
    def gateway(self) -> str:
        self._check_info()
        return self._info["gateway"]

    @property
    def apinetwork(self) -> VlanNodeManager:
        self._check_apinetwork()
        return self._apinetwork

    def translate(
        self, fqdns: List[str], reverse: bool = False
    ) -> Iterable[Tuple[str, str]]:
        def translate(node, vlan_id):
            if not reverse:
                splitted = node.split(".")
                splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
                return ".".join(splitted)
            else:
                node = node.replace("-kavlan-%s" % vlan_id, "")
                return node

        return [(fqdn, translate(fqdn, self.vlan_id)) for fqdn in fqdns]

    def attach(self, fqdns: List[str], device: str):
        set_nodes_vlan(self.site, fqdns, device, self.vlan_id)

    def to_enos(self):
        # On the network, the first IP are reserved to g5k machines.
        # For a routed vlan I don't know exactly how many ip are
        # reserved. However, the specification is clear about global
        # vlan: "A global VLAN is a /18 subnet (16382 IP addresses).
        # It is split -- contiguously -- so that every site gets one
        # /23 (510 ip) in the global VLAN address space". There are 12
        # site. This means that we could take ip from 13th subnetwork.
        # Lets consider the strategy is the same for routed vlan. See,
        # https://www.grid5000.fr/mediawiki/index.php/Grid5000:Network#KaVLAN
        #
        # First, split network in /23 this leads to 32 subnetworks.
        # Then, (i) drops the 12 first subnetworks because they are
        # dedicated to g5k machines, and (ii) drops the last one
        # because some of ips are used for specific stuff such as
        # gateway, kavlan server...
        net = {}
        subnets = IPNetwork(self.cidr)
        if self.vlan_id in KAVLAN_LOCAL_IDS:
            # vlan local
            subnets = list(subnets.subnet(24))
            subnets = subnets[4:7]
        else:
            subnets = list(subnets.subnet(23))
            subnets = subnets[13:31]

        # Finally, compute the range of available ips
        ips = IPSet(subnets).iprange()

        net.update(
            roles=self.roles,
            start=str(IPAddress(ips.first)),
            end=str(IPAddress(ips.last)),
            cidr=self.cidr,
            gateway=self.gateway,
            dns=self.dns,
        )
        return [net]

    def __repr__(self):
        return (
            "<G5kVlanNetwork("
            f"roles={self.roles}, "
            f"site={self.site}, "
            f"vlan_id={self.vlan_id})>"
        )


class G5kProdNetwork(G5kVlanNetwork):
    def __init__(self, roles: List[str], id: str, site: str):
        """Representation of an actual Production Network in G5k.

        Note: production network have the "default" uid on the G5K API.

        Args:
            roles: roles/tags to give to this network (set by the application)
            id: the id to give to this network (set by the application)
            site: the site of this network
        """

        super().__init__(roles, id, site, "DEFAULT")

    def translate(
        self, fqdns: List[str], reverse: bool = True
    ) -> Iterable[Tuple[str, str]]:
        return [(f, f) for f in fqdns]

    def attach(self, fqdns: List[str], nic: str):
        # nothing to do
        pass

    def to_enos(self):
        net = {}
        net.update(roles=self.roles, cidr=self.cidr, gateway=self.gateway, dns=self.dns)
        return [net]

    def __repr__(self):
        return "<G5kProdNetwork(" f"roles={self.roles}, " f"site={self.site}"


class G5kSubnetNetwork(G5kNetwork):
    def __init__(self, roles: List[str], id: str, site: str, subnets: List[str]):
        """Representation of a subnet of G5k (/16 or /22).

        .. info::

            Subnets are weird beasts on G5k. Especially /16 networks for
            which you will be given 64 /22 networks and they aren't
            represented in the REST API.

            So we encapsulate this in this object

        Args:
            roles: roles/tags to give to this network (set by the application)
            id: the id to give to this network (set by the application)
            site: the site of this network
            subnets: the actual subnets (list of cidr) given by OAR.
        """
        super().__init__(roles, id, site)
        self.subnets = subnets

        # Lazy load the gateway info
        self._gateway = None

    @property
    def vlan_id(self):
        return None

    @property
    def gateway(self):
        if self._gateway is None:
            self._gateway = get_subnet_gateway(self.site)

    @property
    def cidr(self):
        return None

    @property
    def apinetwork(self):
        return None

    def translate(
        self, fqdns: List[str], reverse: bool = True
    ) -> Iterable[Tuple[str, str]]:
        return [(f, f) for f in fqdns]

    def attach(self, fqdns: List[str], nic: str):
        pass

    def to_enos(self):
        def build_ipmac(subnet):
            network = IPNetwork(subnet)
            ipmac = []
            for ip in list(network[1:-1]):
                _, x, y, z = ip.words
                ipmac.append((str(ip), G5KMACPREFIX + ":%02X:%02X:%02X" % (x, y, z)))
            start_ip, start_mac = ipmac[0]
            end_ip, end_mac = ipmac[-1]
            return start_ip, start_mac, end_ip, end_mac

        enos_networks = []
        for subnet in self.subnets:
            start_ip, start_mac, end_ip, end_mac = build_ipmac(subnet)
            enos_networks.append(
                {
                    "roles": self.roles,
                    "site": self.site,
                    "dns": self.dns,
                    "gateway": self.gateway,
                    "cidr": subnet,
                    "start": start_ip,
                    "end": end_ip,
                    "mac_start": start_mac,
                    "mac_end": end_mac,
                }
            )
        return enos_networks

    def __repr__(self):
        return (
            "<G5kSubnetNetwork("
            f"roles={self.roles}, "
            f"site={self.site}, "
            f"/22={len(self.subnets)}"
        )


class G5kHost:
    """A G5k host."""

    def __init__(
        self,
        fqdn: str,
        roles: List[str],
        primary_network: G5kNetwork,
        secondary_networks: Optional[List[G5kNetwork]] = None,
    ):
        # read only attributes
        self.fqdn = fqdn
        self.roles = roles
        self.primary_network = primary_network
        self.secondary_networks = secondary_networks
        if secondary_networks is None:
            self.secondary_networks = []

        # by default the ssh address is set to the fqdn
        # this might change if the node is on a vlan
        self._ssh_address: Optional[str] = None
        self._apinode: Optional[RESTObject] = None

        # Trigger any state change on the Grid'5000 side to reflect this object
        # - eg put the node in the vlan
        # .self.mirror_state()

    @property
    def ssh_address(self):
        """Get an SSH reachable address for this Host.

        This may differ from the fqdn when using vlans.

        Returns:
            The address as a string.
        """
        if self._ssh_address is None:
            return self.fqdn
        else:
            return self._ssh_address

    @ssh_address.setter
    def ssh_address(self, address: str):
        """Sets an ssh address for this node.

        You aren't supposed to call this unless you know what you're doing.
        The G5k provider is calling this to set the right name.
        """
        self._ssh_address = address

    @property
    def _where(self) -> Tuple[str, str, str]:
        """Get site cluster and uid for this node.

        Returns:
            (site, cluster, uid)
        """
        uid, site = self.fqdn.split(".")[0:2]
        cluster = self.fqdn.split(".")[0].split("-")[0]
        return site, cluster, uid

    @property
    def apinode(self):
        """Get the api Node object.

        Return:
            Node object (see python-grid500)
        """
        if self._apinode is None:
            self._apinode = get_node(*self._where)
        return self._apinode

    @property
    def primary_nic(self) -> Tuple[str, str]:
        """Get the first nic mounted.

        On Grid'5000 there's only one nic mounted by default: this is the
        primary nic.

        Returns:
            A tuple of (legacy name, deterministic name) for the network card.
        """
        nics = self.get_nics(extra_cond=lambda nic: nic["mounted"])
        return nics[0]

    @property
    def _all_secondary_nics(self) -> List[Tuple[str, str]]:
        """Get mountable nics to serve as secondary interfaces.

        Returns:
            All the nic that can serve as extra network connection.
        """
        return self.get_nics(extra_cond=lambda nic: not nic["mounted"])

    @property
    def secondary_nics(self) -> List[Tuple[str, str]]:
        """Get the nics that serves as secondary nics.

        Note: only return those eligible to map a secondary network.

        Returns:
            All the nic that serves to connect the node to a secondary network.
        """
        return [
            nic for (_, nic) in zip(self.secondary_networks, self._all_secondary_nics)
        ]

    def dhcp_networks_command(self) -> str:
        """Get the command to set up the dhcp an all interfaces.

        Returns:
            The command as a string.
        """
        if len(self.secondary_networks) == 0:
            return ""

        if len(self.secondary_networks) > len(self._all_secondary_nics):
            raise ValueError("There's not enough NIC on the node {self.fqdn}")

        ifconfig = []
        dhcp = []
        for _, (_, nic) in zip(self.secondary_networks, self._all_secondary_nics):
            ifconfig.append(f"ip link set {nic} up")
            dhcp.append(f"dhclient {nic}")
        cmd = "%s ; %s" % (";".join(ifconfig), ";".join(dhcp))
        return cmd

    def grant_root_access_command(self) -> str:
        """ Get the command to get root access on the node."""
        cmd = ["cat ~/.ssh/id_rsa.pub ~/.ssh/authorized_keys"]
        cmd.append("sudo-g5k tee -a /root/.ssh/authorized_keys")
        return "|".join(cmd)

    def get_nics(
        self, extra_cond: Callable[[Dict], bool] = lambda nic: True
    ) -> List[Tuple[str, str]]:
        """Get the network interfaces names corresponding to a criteria.

        .. note::

            - Only the mountable and Ehernet interfaces are returned.
            - Nic are sorted so that the result is fixed accros run.

        Args:
            extra_cond: predicate over a nic to further filter the results.
                Here a nic is a dictionnary as returned in the API.

        NOTE(msimonin): Since 05/18 nics on g5k nodes have predictable names but
        the api description keeps the legacy name (device key) and the new
        predictable name (key name).  The legacy names is still used for api
        request to the vlan endpoint This should be fixed in
        https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=9272
        When its fixed we should be able to only use the new predictable name.

        Args:
            extra_cond(lambda): boolean lambda that takes the nic(dict) as
                parameter

        Returns:
            An list of nics.
            Each nic is a tuple (legacy name, deterministic name)(
            e.g ("eth0", "eno1")
            Result is sorted (ensure idempotence)

        """
        nics = [
            (nic["device"], nic["name"])
            for nic in self.apinode.network_adapters
            if nic["mountable"]
            and nic["interface"] == "Ethernet"
            and not nic["management"]
            and extra_cond(nic)
        ]
        nics = sorted(nics)
        return nics

    def mirror_state(self):
        """Make sure the API states are consistent to the Host attributes.

        For instance this will set some of the NIC of the nodes in a vlan (POST
        request on the API).
        For now the only strategy to map NIC to secondary network is to map
        them in the same order : nic_i <-> seconday_networks[i].
        (where nic_i is not the primary one)

        Note that this doesn't configure the NIC on the node itself (e.g dhcp).
        """
        # Handle vlans for secondary networks
        if len(self.secondary_networks) > len(self._all_secondary_nics):
            raise ValueError("There's not enough NIC on the node {self.fqdn}")
        for net, (eth, _) in zip(self.secondary_networks, self._all_secondary_nics):
            # NOTE(msimonin): in the global vlan case the site of the nodes and
            # the site of the vlan may differ.
            # The site is known in the context of a concrete network.
            net.attach([self.fqdn], eth)

    def __repr__(self):
        return (
            "<G5kHost("
            f"roles={self.roles}, "
            f"fqdn={self.fqdn}, "
            f"ssh_address={self.ssh_address}, "
            f"primary_network={self.primary_network}, "
            f"secondary_networks={self.secondary_networks})>"
        )
