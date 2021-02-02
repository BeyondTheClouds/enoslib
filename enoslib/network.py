from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address
from typing import Iterable, List, Union

NetworkType = Union[IPv4Network, IPv6Network]
AddressType = Union[IPv4Address, IPv6Address]


class Network(object):
    def __init__(self, roles: List[str], network: NetworkType):
        self.roles = roles
        self.network = network

    def has_free_ips(self):
        return False

    def free_ips(self) -> Iterable[AddressType]:
        return []

    def has_free_macs(self):
        return False

    def free_macs(self) -> Iterable[str]:
        return []