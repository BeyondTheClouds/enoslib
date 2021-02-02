import ipaddress
from typing import Iterable, List

from netaddr.ip.sets import IPNetwork, IPSet

from enoslib.network import Network, NetworkType, AddressType
from enoslib.infra.enos_g5k.constants import G5KMACPREFIX, KAVLAN_LOCAL_IDS


class G5kEnosProdNetwork(Network):
    """Implementation of the generic network type.

    Support Both Ipv4 and IPv6 production network
    """

    def has_free_ips(self):
        return False

    def has_free_macs(self):
        return False


class G5kEnosVlan4Network(Network):
    """IPv4 and IPv6 networks are similar but different in G5K.

    So we specialize this class for Ipv4 kavlan
    See G5kEnosVlan6Network for Ipv6 network
    """

    def __init__(self, roles: List[str], network: NetworkType, vlan_id: str):
        super().__init__(roles, network)
        self.vlan_id = vlan_id

    """IpV4 or IpV6."""

    def has_free_ips(self):
        return True

    def free_ips(self) -> Iterable[AddressType]:
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
        subnets = IPNetwork(str(self.network))
        if self.vlan_id in KAVLAN_LOCAL_IDS:
            # vlan local
            subnets = list(subnets.subnet(24))
            subnets = subnets[4:7]
        else:
            subnets = list(subnets.subnet(23))
            subnets = subnets[13:31]

        # Finally, compute the range of available ips
        # and yield in the standard ipaddress world
        for addr in IPSet(subnets).iprange():
            yield ipaddress.ip_address(addr)


class G5kEnosVlan6Network(G5kEnosVlan4Network):
    """
    https://www.grid5000.fr/w/IPv6#The_interface_part

    In my understanding taking a E part greater than max(cluster_index,
    site_index) will give us some free ips.
    """

    def free_ips(self):
        subnets = IPNetwork(str(self.network))
        start = subnets.network + 256
        subnet = IPNetwork(f"{start}/70")
        for addr in subnet.iter_hosts():
            yield ipaddress.ip_address(addr.value)


def build_ipmac(subnet):
    network = IPNetwork(subnet)
    for ip in list(network[1:-1]):
        _, x, y, z = ip.words
        ip, mac = (str(ip), G5KMACPREFIX + ":%02X:%02X:%02X" % (x, y, z))
        yield ip, mac


class G5kEnosSubnetNetwork(Network):
    """G5k subnet model

    IPv4 only for now.
    """

    def has_free_ips(self):
        return True

    def free_ips(self):
        for ip, _ in build_ipmac(str(self.network)):
            yield ipaddress.ip_address(ip)

    def has_free_macs(self):
        return True

    def free_macs(self):
        for _, mac in build_ipmac(str(self.network)):
            yield mac
