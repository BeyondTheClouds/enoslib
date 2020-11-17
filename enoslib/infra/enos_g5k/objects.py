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
        if self.vlan_id is None:
            return True
        if other.vlan_id is None:
            return False
        return self.vlan_id < other.vlan_id

    @property
    def dns(self):
        if self._dns is None:
            self._dns = get_dns(self.site)
        return self._dns

    @property
    @abstractmethod
    def apinetwork(self) -> Optional[RESTObject]:
        pass

    @property
    @abstractmethod
    def vlan_id(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def gateway(self) -> Optional[str]:
        pass

    @property
    @abstractmethod
    def cidr(self) -> Optional[str]:
        pass

    @abstractmethod
    def translate(self, fqdns: List[str], reverse=True) -> Iterable[Tuple[str, str]]:
        pass

    @abstractmethod
    def attach(self, fqdns: List[str], device: str):
        pass

    @abstractmethod
    def to_enos(self) -> List[Dict]:
        pass

    def add_host(self, host: "G5kHost"):
        # attach here ?
        self.hosts.append(host)

    def add_hosts(self, hosts: List["G5kHost"]):
        # attach here ?
        self.hosts.extend(hosts)


class G5kVlanNetwork(G5kNetwork):
    def __init__(self, roles: List[str], id: str, site: str, vlan_id: str):
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
        nodes = [n[1] for n in self.translate(fqdns)]
        set_nodes_vlan(self.site, nodes, device, self.vlan_id)

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


class G5kProdNetwork(G5kVlanNetwork):
    def __init__(self, roles: List[str], id: str, site: str):
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


class G5kSubnetNetwork(G5kNetwork):
    def __init__(self, roles: List[str], id: str, site: str, subnets: List[str]):
        # we shallow copy the list which makes mypy happy
        # https://mypy.readthedocs.io/en/latest/common_issues.html#variance
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
                    "network": subnet,
                    "start": start_ip,
                    "end": end_ip,
                    "mac_start": start_mac,
                    "mac_end": end_mac,
                }
            )
        return enos_networks


class G5kHost:
    """A G5k host."""

    def __init__(
        self,
        fqdn: str,
        roles: List[str],
        primary_network: G5kNetwork,
        secondary_networks: List[G5kNetwork],
    ):
        # read only attributes
        self.fqdn = fqdn
        self.roles = roles
        self.primary_network = primary_network
        self.secondary_networks = secondary_networks

        # by default the ssh address is set to the fqdn
        # this might change if the node is on a vlan
        self.__ssh_address: Optional[str] = None
        self.__apinode: Optional[RESTObject] = None

        # Trigger any state change on the Grid'5000 side to reflect this object
        # - eg put the node in the vlan
        # .self.mirror_state()

    @property
    def ssh_address(self):
        if self.__ssh_address is None:
            return self.fqdn
        else:
            return self.__ssh_address

    @ssh_address.setter
    def ssh_address(self, address: str):
        self.__ssh_address = address

    @property
    def where(self) -> Tuple[str, str, str]:
        """Get site cluster and uid for this node.

        Returns:
            (site, cluster, uid)
        """
        uid, site = self.fqdn.split(".")[0:2]
        cluster = self.fqdn.split(".")[0].split("-")[0]
        return site, cluster, uid

    @property
    def apinode(self):
        """Get the api Node object."""
        if self.__apinode is None:
            self.__apinode = get_node(*self.where)
        return self.__apinode

    @property
    def primary_nic(self):
        """Get the first nic mounted.

        On Grid'5000 there's only one nic mounted by default: this is the
        primary nic.
        """
        nics = self._get_nics(extra_cond=lambda nic: nic["mounted"])
        return nics[0]

    @property
    def secondary_nics(self):
        """Get mountable nics to serve as secondary interfaces."""
        return self._get_nics(extra_cond=lambda nic: not nic["mounted"])

    def dhcp_networks_command(self):
        """Get the command to set up the dhcp an all interfaces.

        Args:
            TODO network_roles: get the command for these roles only.
                None means all roles
        """
        if len(self.secondary_networks) == 0:
            return ""

        if len(self.secondary_networks) > len(self.secondary_nics):
            raise ValueError("There's not enough NIC on the node {self.fqdn}")

        ifconfig = []
        dhcp = []
        for _, (_, nic) in zip(self.secondary_networks, self.secondary_nics):
            ifconfig.append(f"ip link set {nic} up")
            dhcp.append(f"dhclient {nic}")
        cmd = "%s ; %s" % (";".join(ifconfig), ";".join(dhcp))
        return cmd

    def grant_root_access_command(self):
        cmd = ["cat ~/.ssh/id_rsa.pub ~/.ssh/authorized_keys"]
        cmd.append("sudo-g5k tee -a /root/.ssh/authorized_keys")
        cmd = "|".join(cmd)
        return cmd

    def _get_nics(
        self, extra_cond: Callable[[Dict], bool] = lambda nic: True
    ) -> Iterable[Tuple[str, str]]:
        """Get the network interfaces names corresponding to a criteria.

        Note that the cluster is passed (not the individual node names), thus it is
        assumed that all nodes in a cluster have the same interface names same
        configuration. In addition to ``extra_cond``, only the mountable and
        Ehernet interfaces are returned.

        NOTE(msimonin): Since 05/18 nics on g5k nodes have predictable names but
        the api description keep the legacy name (device key) and the new
        predictable name (key name).  The legacy names is still used for api
        request to the vlan endpoint This should be fixed in
        https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=9272
        When its fixed we should be able to only use the new predictable name.

        Args:
            extra_cond(lambda): boolean lambda that takes the nic(dict) as
                parameter

        Returns:
            An Iterable of nics.
            Each nic is a tuple (legacy name, deterministic name).
            E.g ("eth0", "eno1")
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
        """Make sure the API states are consistent to the Host attributes."""
        # Handle vlans for secondary networks
        if len(self.secondary_networks) > len(self.secondary_nics):
            raise ValueError("There's not enough NIC on the node {self.fqdn}")
        for net, (eth, _) in zip(self.secondary_networks, self.secondary_nics):
            # NOTE(msimonin): in the global vlan case the site of the nodes and
            # the site of the vlan may differ.
            # The site is known in the context of a concrete network.
            net.attach([self.fqdn], eth)
