# -*- coding: utf-8 -*-
import copy
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import InitVar, dataclass, field
from ipaddress import (IPv4Address, IPv4Network, IPv6Address, IPv6Interface,
                       IPv6Network, ip_interface, ip_network)
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

NetworkType = Union[bytes, int, Tuple, str]
AddressInterfaceType = Union[IPv4Address, IPv6Address]


def _ansible_map_network_device(
    provider_nets: List["Network"], devices: List[Dict]
) -> List[Tuple["Network", "IPAddress"]]:
    """Map networks to ansible devices."""
    matches = []
    for provider_net in provider_nets:
        for device in devices:
            versions = ["ipv4", "ipv6"]
            for version in versions:
                if version not in device:
                    continue
                ips = device[version]
                if not isinstance(ips, list):
                    ips = [ips]
                if len(ips) < 1:
                    continue
                for ip in ips:
                    host_addr = IPAddress.from_ansible(
                        ip, roles=provider_net.roles, device=device["device"]
                    )
                    if host_addr.ip in provider_net.network:
                        # found a map between a device on the host and a network
                        matches.append((provider_net, host_addr))
    return matches


class Network(ABC):
    def __init__(self, roles: List[str], address: NetworkType):
        self.roles = roles
        self.network = ip_network(address)

    @property
    @abstractmethod
    def gateway(self) -> Optional[AddressInterfaceType]:
        ...

    @property
    @abstractmethod
    def dns(self) -> Optional[AddressInterfaceType]:
        ...

    @property
    @abstractmethod
    def has_free_ips(self):
        return False

    @property
    @abstractmethod
    def free_ips(self) -> Iterable[AddressInterfaceType]:
        yield from ()

    @property
    @abstractmethod
    def has_free_macs(self):
        return False

    @property
    @abstractmethod
    def free_macs(self) -> Iterable[str]:
        yield from ()


class DefaultNetwork(Network):
    @property
    def gateway(self) -> Optional[AddressInterfaceType]:
        return None

    @property
    def dns(self) -> Optional[AddressInterfaceType]:
        return None

    @property
    def has_free_ips(self):
        return False

    @property
    def free_ips(self) -> Iterable[AddressInterfaceType]:
        yield from ()

    @property
    def has_free_macs(self):
        return False

    @property
    def free_macs(self) -> Iterable[str]:
        yield from ()


@dataclass(unsafe_hash=True)
class IPAddress(object):
    """Representation of an address on a node.

    Usually the same ip_address can't be assigned twice.
    So equality and hash are based only on the ip field.
    """

    address: InitVar[Union[bytes, int, Tuple, str]]
    roles: List[str] = field(compare=False, hash=False)
    device: str = field(compare=False, hash=False)

    # computed
    ip: Optional[Union[IPv4Address, IPv6Interface]] = field(
        default=None, init=False, compare=True, hash=True
    )

    def __post_init__(self, address):
        # transform to ip interface
        self.ip = ip_interface(address)

    @classmethod
    def from_ansible(cls, d: Dict, roles: List[str], device: str):
        """Build an IPAddress from ansible fact.

        Ansible fact corresponding section can be:
        - ipv4: {"address": ..., "netmask": ..., "broadcast": ..., }
        - ipv6: {"address": ..., "prefix": ..., "scope": ...}
        """
        keys_1 = {"address", "netmask"}
        keys_2 = {"address", "prefix"}
        if keys_1.issubset(d.keys()):
            return cls((d["address"], d["netmask"]), roles, device)
        elif keys_2.issubset(d.keys()):
            return cls(f"{d['address']}/{d['prefix']}", roles, device)
        else:
            raise ValueError(f"Nor {keys_1} not {keys_2} found in the dictionnary")


@dataclass(unsafe_hash=True)
class Host(object):
    """Abstract unit of computation.

    A Host is anything EnosLib can SSH to and run shell commands on.
    It is an abstraction notion of unit of computation that can be
    bound to bare-metal machines, virtual machines, or containers.

    """

    address: str
    alias: Optional[str] = field(default=None)
    user: Optional[str] = None
    keyfile: Optional[str] = None
    port: Optional[int] = None
    # Two Hosts have the same hash if we can SSH on each of them in
    # the same manner (don't consider extra info in `__hash__()` that
    # are added, e.g., by enoslib.api.discover_networks).
    extra: Dict = field(default_factory=dict, hash=False)
    # Hold a list of known ip addresses
    # - discover_network can set this for you
    # - also there's a plan to make the provider fill that for you when
    #   possible (e.g in G5K we can use the REST API)
    extra_addresses: Set[IPAddress] = field(default_factory=set, hash=False)

    def __post_init__(self):
        if not self.alias:
            self.alias = self.address

        # we make a copy to avoid to share the reference to extra outside
        # see for example https://gitlab.inria.fr/discovery/enoslib/-/issues/74
        if self.extra is not None:
            self.extra = copy.deepcopy(self.extra)

        if self.extra_addresses is None:
            self.extra_addresses = set()

    def to_dict(self):
        return copy.deepcopy(self.__dict__)

    def add_address(self, address: IPAddress):
        """Add an ip address to this host.

        If the IP already exists, replace it with the new value.

        Args:
            address: The ip address to add (or update)
        """
        try:
            self.extra_addresses.remove(address)
        except KeyError:
            pass
        self.extra_addresses.add(address)

    def set_addresses_from_ansible(
        self, networks: List[Network], host_facts: Dict, clear: bool = True
    ):
        """Set the ip_addresses based on ansible fact.

        Mutate self, since it add/update the list of network addresses
        """

        def get_devices(facts):
            """Extract the network devices information from the facts."""
            devices = []
            for interface in facts["ansible_interfaces"]:
                ansible_interface = "ansible_" + interface
                # filter here (active/ name...)
                if "ansible_" + interface in facts:
                    interface = facts[ansible_interface]
                    devices.append(interface)
            return devices

        if clear:
            self.extra_addresses = set()
        matches = _ansible_map_network_device(networks, get_devices(host_facts))
        for _, addr in matches:
            self.add_address(addr)

    def get_network_roles(self):
        """Index the address by network roles."""
        roles = defaultdict(list)
        for address in self.extra_addresses:
            for role in address.roles:
                roles[role].append(address)
        return roles

    @classmethod
    def from_dict(cls, d):
        _d = copy.deepcopy(d)
        address = _d.pop("address")
        return cls(address, **_d)

    def to_host(self):
        """Copy or coerce to a Host."""
        return Host(
            self.address,
            alias=self.alias,
            user=self.user,
            keyfile=self.keyfile,
            port=self.port,
            extra=self.extra,
        )

    def __str__(self):
        args = [
            self.alias,
            "address=%s" % self.address,
            "user=%s" % self.user,
            "keyfile=%s" % self.keyfile,
            "port=%s" % self.port,
            "extra=%s" % self.extra,
        ]
        return "Host(%s)" % ", ".join(args)
