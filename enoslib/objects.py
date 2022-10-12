"""
.. _objects:

These modules are made of the **library-level** objects. These are provider
agnostic objects that can be fed into most of the |enoslib| functions.

Currently, the main abstractions of this module are the
:py:class:`~enoslib.objects.Host` and the :py:class:`~enoslib.objects.Network`.
They abstract away the notion of compute servers (something you can access and
run some actions on) and networks (something you can get IPs from). Grouping
resources is done using the :py:class:`~enoslib.objects.Roles` and
:py:class:`~enoslib.objects.Networks` (plural).

Most likely you'll interact with ``Roles`` and ``Networks`` right after calling
``provider.init()``: this is indeed a provider responsibility to turn your
abstract resource description into concrete library level objects.
"""
import copy
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv6Address,
    IPv6Interface,
    ip_address,
    ip_interface,
)
from itertools import islice
from pathlib import Path
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from netaddr import EUI


from .collections import ResourcesSet, RolesDict
from enoslib.html import (
    dict_to_html_foldable_sections,
    html_to_foldable_section,
    html_from_dict,
    html_from_sections,
    repr_html_check,
)

NetworkType = Union[bytes, int, str]
AddressType = Union[bytes, int, str]
AddressInterfaceType = Union[IPv4Address, IPv6Address]

Role = str
RolesNetworks = Tuple["Roles", "Networks"]

# Many actions (run, actions, ...) on hosts can be fed with
# Roles (e.g. coming from provider.init)
# Iterable[Host] (e.g. coming from Roles filtering)
# in order to make those actions more convenient to use we'd like to allow
# some flexible inputs to be used.
RolesLike = Union["Roles", Iterable["Host"], "Host"]

PathLike = Union[Path, str]


def _build_devices(facts, networks):
    """Extract the network devices information from the facts."""
    devices = set()
    for interface in facts["ansible_interfaces"]:
        ansible_interface = "ansible_" + interface
        # filter here (active/ name...)
        if ansible_interface in facts:
            devices.add(NetDevice.sync_from_ansible(facts[ansible_interface], networks))
    return devices


class Network(ABC):
    """Base class for the library level network abstraction.

    When one calls init on a provider, one takes ownership on nodes and
    networks. This class reflect one network owned by the user for the
    experiment lifetime. IPv4 and IPv6 networks can be represented by such
    object.

    Providers *must* inherit from this class or the
    :py:class:`DefaultNetwork` class which provides a good enough
    implementation in most cases.

    Indeed, currently provenance (which provider created this) is encoded in
    the __class__ attribute.
    """

    def __init__(self, address: NetworkType):
        # accept cidr but coerce to IPNetwork
        self.network = ip_interface(address).network
        self.alias = str(self.network)

    def __eq__(self, other) -> bool:
        if self.__class__ != other.__class__:
            return False
        return self.network == other.network

    def __lt__(self, other) -> bool:
        return self.network.version < other.network.version and self.network.__lt__(
            other.network
        )

    def __hash__(self):
        return hash(self.network)

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
    """Good enough implementation of Network for most situations.

    Provides pooling for contiguous ips and/or macs.
    Support IPv4 and IPv6.

    Providers *must* inherit from this class.

    Args:
        address  : network address (as in ipaddress.ip_interface)
        gateway  : (optional) the gateway for this network
                   (as in ipaddress.ip_address)
        dns      : (optional) the dns address
                   (as in ipaddress.ip_address)
        ip_start : (optional) first ip in the ip pool
                   (as in ipaddress.ip_address)
        ip_end   : (optional) last ip in the ip pool
                   (as in ipaddress.ip_address)
        mac_start: (optional) first mac in the mac pool
                   (as in netaddr.EUI)
        mac_end  : (optional) last mac in the mac pool
                   (as in netaddr.EUI)
    """

    def __init__(
        self,
        address: NetworkType,
        gateway: Optional[str] = None,
        dns: Optional[str] = None,
        ip_start: Optional[AddressType] = None,
        ip_end: Optional[AddressType] = None,
        mac_start: str = None,
        mac_end: str = None,
    ):

        super().__init__(address=address)
        self._gateway = None
        if gateway is not None:
            self._gateway = ip_address(gateway)
        self._dns = None
        if self._dns is not None:
            self._dns = ip_address(dns)
        self.pool_start = None
        if ip_start is not None:
            self.pool_start = ip_address(ip_start)
        self.pool_end = None
        if ip_end is not None:
            self.pool_end = ip_address(ip_end)
        self.pool_mac_start: Optional[EUI] = None
        if mac_start is not None:
            self.pool_mac_start = EUI(mac_start)
        self.pool_mac_end: Optional[EUI] = None
        if mac_end is not None:
            self.pool_mac_end = EUI(mac_end)

    @property
    def gateway(self) -> Optional[AddressInterfaceType]:
        return self._gateway

    @property
    def dns(self) -> Optional[AddressInterfaceType]:
        return self._dns

    @property
    def has_free_ips(self) -> bool:
        return (
            self.pool_start is not None
            and self.pool_end is not None
            and self.pool_start.packed < self.pool_end.packed  # Workaround type check
        )

    @property
    def free_ips(self) -> Iterable[AddressInterfaceType]:
        if self.has_free_ips:
            assert self.pool_start is not None
            assert self.pool_end is not None
            for i in range(int(self.pool_start), int(self.pool_end)):
                yield ip_address(i)
        yield from ()

    @property
    def has_free_macs(self) -> bool:
        return (
            self.pool_mac_start is not None
            and self.pool_mac_end is not None
            and self.pool_mac_start < self.pool_mac_end
        )

    @property
    def free_macs(self) -> Iterable[EUI]:
        if self.has_free_macs:
            assert self.pool_mac_start is not None
            assert self.pool_mac_end is not None
            for item in range(int(self.pool_mac_start), int(self.pool_mac_end)):
                yield EUI(item)
        yield from ()

    @repr_html_check
    def _repr_html_(self, content_only=False):
        """
        content_only == True  => html_object == <div class=enoslib>...</div>
        content_only == False => html_base(html_object) == css +
        """
        ips = list(islice(self.free_ips, 0, 10, 1))
        if len(ips) > 0:
            ips += ["[truncated list]"]
        macs = list(islice(self.free_macs, 0, 10, 1))
        if len(macs) > 0:
            macs += ["[truncated list]"]
        d = {
            "network": self.network,
            "gateway": self.gateway,
            "dns": self.dns,
            "free_ips": ips,
            "free_macs": macs,
        }

        name_class = f"{str(self.__class__)}@{hex(id(self))}"
        return html_from_dict(name_class, d, content_only=content_only)


class NetworksView(ResourcesSet):
    """A specialization of :py:class:`~enoslib.collections.ResourceSet`

    for :py:class:`~enoslib.objects.Networks`.
    """

    inner = Network


class Networks(RolesDict):
    """A specialization of :py:class:`~enoslib.collections.RolesDict`

    for :py:class:`~enoslib.objects.NetworksView`.
    """

    inner = NetworksView

    # TODO(msimonin): This is still duplicated code between Roles and Networks
    # but should be de-deduplicated using a common ancestor for networks and roles
    @repr_html_check
    def _repr_html_(self, content_only=False):
        repr_title = f"{str(self.__class__)}@{hex(id(self))}"
        role_contents = []
        for role, networks in self.data.items():
            repr_networks = []
            for network in networks:
                repr_networks.append(
                    html_to_foldable_section(
                        network.network, network._repr_html_(content_only=True)
                    )
                )
            role_contents.append(
                html_to_foldable_section(role, repr_networks, str(len(self.data[role])))
            )
        return html_from_sections(repr_title, role_contents, content_only=content_only)


@dataclass(unsafe_hash=True)
class IPAddress:
    """Representation of an address on a node.

    Usually the same ip_address can't be assigned twice. So equality and hash
    are based on the ip field. Moreover, in the case where two providers
    network span the same ip range equality is also based on the network
    provenance.
    """

    address: InitVar[Union[bytes, int, Tuple, str]]
    network: Optional[Network] = field(default=None, compare=True, hash=True)

    # computed
    ip: Optional[Union[IPv4Interface, IPv6Interface]] = field(
        default=None, init=False, compare=True, hash=True
    )

    def __post_init__(self, address):
        # transform to ip interface
        self.ip = ip_interface(address)

    @classmethod
    def from_ansible(cls, d: Dict, network: Optional[Network]):
        """Build an IPAddress from ansible fact.

        Ansible fact corresponding section can be:
        - ipv4: {"address": ..., "netmask": ..., "broadcast": ..., }
        - ipv6: {"address": ..., "prefix": ..., "scope": ...}
        """
        keys_1 = {"address", "netmask"}
        keys_2 = {"address", "prefix"}
        if keys_1.issubset(d.keys()):
            # there's a bug/feature in early python3.7, and the second argument
            # is actually the prefix length
            # https://bugs.python.org/issue27860
            # cls((d["address"], d["netmask"])), device)
            return cls(f"{d['address']}/{d['netmask']}", network)
        elif keys_2.issubset(d.keys()):
            return cls(f"{d['address']}/{d['prefix']}", network)
        else:
            raise ValueError(f"Nor {keys_1} not {keys_2} found in the dictionary")

    def to_dict(self):
        return dict(ip=str(self.ip))


@dataclass(unsafe_hash=True)
class NetDevice:
    """A network device.

    Note: two NetDevices are equal iff they have the same name and all the
    addresses are equals.
    """

    name: str = field(compare=True, hash=True)
    addresses: Set[IPAddress] = field(default_factory=set, compare=True, hash=False)

    @classmethod
    def sync_from_ansible(cls, device: Dict, networks: Networks):
        """

        "ansible_br0": {
            "ipv4": {
                "address": "172.16.99.11",
                "broadcast": "172.16.111.255",
                "netmask": "255.255.240.0",
                "network": "172.16.96.0"
            },
            "ipv4_secondaries": [
                {
                    "address": "10.158.0.2",
                    "broadcast": "",
                    "netmask": "255.255.252.0",
                    "network": "10.158.0.0"
                }
            ],
            "ipv6": [{...}
            ]
        }
        """
        # build all ips
        addresses = set()
        keys = ["ipv4", "ipv4_secondaries", "ipv6"]
        for version in keys:
            if version not in device:
                continue
            ips = device[version]
            if not isinstance(ips, list):
                ips = [ips]
            if len(ips) < 1:
                continue
            for ip in ips:
                _net = None
                for _, provider_nets in networks.items():
                    for provider_net in provider_nets:
                        # build an IPAddress /a priori/
                        addr = IPAddress.from_ansible(ip, provider_net)
                        if addr.ip in provider_net.network:
                            _net = provider_net
                addresses.add(IPAddress.from_ansible(ip, _net))
        # addresses contains all the addresses for this devices
        # even those that doesn't correspond to an enoslib network

        # detect if that's a bridge
        if device["type"] == "bridge":
            return BridgeDevice(
                name=device["device"], addresses=addresses, bridged=device["interfaces"]
            )
        else:
            # regular "ether"
            return cls(name=device["device"], addresses=addresses)

    @property
    def interfaces(self) -> List[str]:
        return [self.name]

    def filter_addresses(
        self,
        networks: Optional[Iterable[Network]] = None,
        include_unknown: bool = False,
    ) -> List[IPAddress]:
        """Filter address based on the passed network list.

        Args:
            networks: a list of networks to further filter the request
                      If None or [], all the interfaces with at least one
                      network attached will be returned. This doesn't return
                      interfaces attached to network unknown from EnOSlib.
            include_unknown: True iff we want all the interface that are not
                      attached to an EnOSlib network. Ignored if ``networks`` is not
                      None.

        Return:
            A list of addresses
        """
        if networks:
            # return only known addresses
            return [
                addr
                for addr in self.addresses
                for network in networks
                if addr.ip in network.network
            ]
        # return all the addresses known to enoslib (those that belong to one network)
        addresses = [addr for addr in self.addresses if addr.network is not None]
        if include_unknown:
            # we return all addresses
            return addresses + [addr for addr in self.addresses if addr.network is None]
        return addresses

    def to_dict(self):
        return dict(
            device=self.name,
            addresses=[address.to_dict() for address in self.addresses],
            type="ether",
        )

    @repr_html_check
    def _repr_html_(self, content_only=False):
        d = self.to_dict()
        name_class = f"{str(self.__class__)}@{hex(id(self))}"
        return html_from_dict(name_class, d, content_only=content_only)


@dataclass(unsafe_hash=True)
class BridgeDevice(NetDevice):
    bridged: List[str] = field(default_factory=list, compare=False, hash=False)

    @property
    def interfaces(self) -> List[str]:
        """Get all the interfaces that are bridged here."""
        return self.bridged

    def to_dict(self):
        d = super().to_dict()
        d.update(type="bridge", interfaces=self.interfaces)
        return d


@dataclass()
class Processor:
    cores: int
    count: int
    threads_per_core: int

    def __post_init__(self):
        self.vcpus = self.cores * self.count * self.threads_per_core

    def to_dict(self):
        return {
            "cores": self.cores,
            "count": self.count,
            "threads_per_core": self.threads_per_core,
        }

    @repr_html_check
    def _repr_html_(self, content_only: bool = False):
        d = self.to_dict()
        return dict_to_html_foldable_sections(d)


class BaseHost:
    pass


@dataclass(unsafe_hash=True, order=True)
class Host(BaseHost):
    """Abstract unit of computation.

    A Host is anything EnosLib can access (e.g. using SSH) to and run shell
    commands on. It is an abstraction notion of unit of computation that can
    be bound to bare-metal machines, virtual machines, or containers.


    Note:

        Internally EnOSlib is using Ansible to connect to the remote hosts.
        By default, SSH is used but it isn't the only connection method
        supported. You can change the connection method to fit your needs by
        setting the `ansible_connection` key in the extra field (and other
        options if needed).
        Ref: https://docs.ansible.com/ansible/latest/plugins/connection.html

    Args:
        address: host will be reached at this address (using SSH by default).
        alias: a human-readable alias
        user: user to connect with (e.g. using SSH)
        keyfile: keyfile to use to authenticate (e.g. when using SSH)
        port: port to connect to (e.g. using SSH)
        extra: dictionary of options. Will be passed to Ansible as host_vars.
            Mutation of this attribute is possible and must be performed using the
            :py:meth:`~enoslib.objects.Host.set_extra` or
            :py:meth:`~enoslib.objects.Host.reset_extra`
        net_devices: list of network devices configured on this host.
            can be synced with the :py:func:`enoslib.api.sync_network_info`.

    Note:
        In the future we'd like the provider to populate the net_devices
        to get a consistent initial representation of the hosts.
    """

    address: str = field(compare=True)
    alias: Optional[str] = field(default=None)
    user: Optional[str] = None
    keyfile: Optional[str] = None
    port: Optional[int] = None
    # Two Hosts have the same hash if we can SSH on each of them in
    # the same manner (don't consider extra info in `__hash__()` that
    # are added, e.g., by enoslib.api.sync_network_info).
    extra: Dict = field(default_factory=dict, hash=False)
    # Hold a list of known ip addresses
    # - discover_network can set this for you
    # - also there's a plan to make the provider fill that for you when
    #   possible (e.g. in G5K we can use the REST API)
    net_devices: Set[NetDevice] = field(default_factory=set, hash=False)
    __original_extra: Dict = field(default_factory=dict, init=False, hash=False)

    def __post_init__(self):
        if not self.alias:
            self.alias = self.address

        # we make a copy to avoid to share the reference to extra outside
        # see for example https://gitlab.inria.fr/discovery/enoslib/-/issues/74
        if self.extra is not None:
            self.extra = copy.deepcopy(self.extra)

        if self.net_devices is None:
            self.net_devices = set()
        self.net_devices = set(self.net_devices)

        # write by the sync_from_ansible_method
        # read by specific host accessor (e.g processor, memory)
        self.__facts = None

        # keep track of the original extra vars
        self.__original_extra = copy.deepcopy(self.extra)

    def set_extra(self, **kwargs) -> "Host":
        """Mutate the extra vars of this host."""
        self.extra.update(**kwargs)
        return self

    def reset_extra(self) -> "Host":
        """Recover the extra vars of this host to the original ones."""
        # recover the original extra vars
        self.extra = copy.deepcopy(self.__original_extra)
        return self

    def get_extra(self) -> Dict:
        """Get a copy of the extra vars of this host."""
        return copy.deepcopy(self.extra)

    def to_dict(self):
        p = None
        if self.processor is not None:
            p = self.processor.to_dict()
        d = dict(
            address=self.address,
            alias=self.alias,
            user=self.user,
            keyfile=self.keyfile,
            port=self.port,
            extra=self.extra,
            processor=p,
            net_devices=[device.to_dict() for device in self.net_devices],
        )
        return copy.deepcopy(d)

    def sync_from_ansible(
        self, networks: Networks, host_facts: Dict, clear: bool = True
    ):
        """Set the devices based on ansible fact.s

        Mutate self, since it add/update the list of network devices
        Currently the dict must be compatible with the ansible hosts facts.
        """
        self.__facts = host_facts
        if clear:
            self.net_devices = set()
        self.net_devices = _build_devices(host_facts, networks)
        return self

    def filter_addresses(
        self, networks: Optional[Iterable[Network]] = None, include_unknown=False
    ) -> List[IPAddress]:
        """Get some addresses assigned to this host.

        Args:
            networks: a list of networks to further filter the request
                      If None or [], all the interfaces with at least one
                      network attached will be returned. This doesn't return
                      interfaces attached to network unknown from EnOSlib.
            include_unknown: True iff we want all the interface that are not
                      attached to an EnOSlib network. Ignored if ``networks`` is not
                      None.

        Return:
            A list of addresses
        """
        addresses = []
        for net_device in self.net_devices:
            addresses += net_device.filter_addresses(
                networks, include_unknown=include_unknown
            )
        return addresses

    def filter_interfaces(
        self, networks: Optional[Iterable[Network]] = None, include_unknown=False
    ) -> List[str]:
        """Get some device interfaces.

        Args:
            networks: a list of networks to further filter the request
                      If None, all the interfaces with at least one network attached
                      will be returned. This doesn't return interfaces
                      attached to network unknown from EnOSlib.
            include_unknown: True iff we want all the interface that are not
                      attached to an EnOSlib network. Ignored if ``networks`` is not
                      None.

        Return:
            A list of interface names.
        """
        interfaces = []
        for net_device in self.net_devices:
            if net_device.filter_addresses(networks, include_unknown=include_unknown):
                # at least one address in this network
                # or networks is None and we got all the known addresses
                interfaces.extend(net_device.interfaces)
        return interfaces

    @property
    def processor(self) -> Optional[Processor]:
        if self.__facts is not None:
            cores = self.__facts["ansible_processor_cores"]
            count = self.__facts["ansible_processor_count"]
            tpc = self.__facts["ansible_processor_threads_per_core"]
            return Processor(cores=cores, count=count, threads_per_core=tpc)
        return None

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
            "net_devices=%s" % self.net_devices,
        ]
        return "Host(%s)" % ", ".join(args)

    @repr_html_check
    def _repr_html_(self, content_only=False) -> str:
        name_class = f"{str(self.__class__)}@{hex(id(self))}"
        d = self.to_dict()
        # trick to not nest dictionary
        d.pop("net_devices")
        d.pop("processor")
        sections = [dict_to_html_foldable_sections(d)]
        net_d = []
        for n in self.net_devices:
            n_html = n._repr_html_(content_only=True)
            net_d.append(html_to_foldable_section(n.name, n_html))
        sections.append(
            html_to_foldable_section("net_devices", net_d, extra=str(len(net_d)))
        )
        p = self.processor
        if p:
            # Display a quick summary of the available processor
            sections.append(
                html_to_foldable_section(
                    "processor",
                    p._repr_html_(content_only=True),
                    extra=f"{p.vcpus} vcpus",
                )
            )
        return html_from_sections(name_class, sections, content_only=content_only)


class HostsView(ResourcesSet):
    """A specialization of :py:class:`~enoslib.collections.ResourcesSet`

    for :py:class:`~enoslib.objects.Host`.
    """

    inner = Host


class Roles(RolesDict):
    """A specialization of :py:class:`~enoslib.collections.RolesDict`

    for :py:class:`~enoslib.objects.HostsView`.
    """

    inner = HostsView

    @repr_html_check
    def _repr_html_(self, content_only=False):
        repr_title = f"{str(self.__class__)}@{hex(id(self))}"
        role_contents = []
        for role, hosts in self.data.items():
            repr_hosts = []
            for h in hosts:
                repr_hosts.append(
                    html_to_foldable_section(h.alias, h._repr_html_(content_only=True))
                )
            role_contents.append(
                html_to_foldable_section(
                    role, repr_hosts, extra=str(len(self.data[role]))
                )
            )
        return html_from_sections(repr_title, role_contents, content_only=content_only)
