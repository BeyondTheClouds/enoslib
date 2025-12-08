from __future__ import annotations

from ipaddress import IPv4Network, IPv6Interface, IPv6Network, ip_network
from typing import Mapping, MutableMapping

from fabrictestbed_extensions.fablib.fablib import FablibManager

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_FLAVOUR,
    DEFAULT_IMAGE,
    DEFAULT_NAME_PREFIX,
    DEFAULT_SITE,
    DEFAULT_USER,
    DEFAULT_WALLTIME,
    FABNETV4,
    FABNETV4EXT,
    FABNETV6,
    FABNETV6EXT,
    FLAVOURS,
    L2BRIDGE,
    L2PTP,
    L2STS,
    L3VPN,
    NIC_MODEL_CONNECTX_6,
    NIC_SHARED,
    NVME,
    PORTMIRROR,
    STORAGE,
)
from .schema import SCHEMA, FabricValidator

V4_SUBNETS = IPv4Network("192.168.0.0/16").subnets(new_prefix=24)

FABNET_V4_SUBNET = FablibManager.FABNETV4_SUBNET

FABNET_V6_SUBNET = FablibManager.FABNETV6_SUBNET

FABNET_EXT_V4_SUBNET = FablibManager.FABNETV4EXT_SUBNET

FABNET_EXT_V6_SUBNET = FablibManager.FABNETV6EXT_SUBNET


class Configuration(BaseConfiguration):
    _SCHEMA = SCHEMA
    _VALIDATOR_FUNC = FabricValidator

    def __init__(self):
        super().__init__()
        self.rc_file = None
        self.walltime = DEFAULT_WALLTIME
        self.site = DEFAULT_SITE
        self.image = DEFAULT_IMAGE
        self.user = DEFAULT_USER
        self.name_prefix = DEFAULT_NAME_PREFIX

        self._machine_cls: type[MachineConfiguration] = MachineConfiguration
        # self._network_cls: type[NetworkConfiguration] = NetworkConfiguration

    @classmethod
    def from_dictionary(
        cls, dictionary: Mapping, validate: bool = True
    ) -> Configuration:
        if validate:
            cls.validate(dictionary)

        self = cls()
        _resources = dictionary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.machines = [MachineConfiguration.from_dictionary(m) for m in _machines]
        self.networks = [networks_from_dictionary(n) for n in _networks]

        for key in ["walltime", "rc_file", "site", "image", "user", "name_prefix"]:
            value = dictionary.get(key)
            if value is not None:
                setattr(self, key, value)

        for machine in self.machines:
            machine.site = machine.site or self.site
            machine.image = machine.image or self.image
            machine.user = machine.user or self.user

        self.finalize()
        return self

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(
            rc_file=self.rc_file,
            site=self.site,
            image=self.image,
            user=self.user,
            name_prefix=self.name_prefix,
            resources={
                "machines": [m.to_dict() for m in self.machines],
                "networks": [n.to_dict() for n in self.networks],
            },
        )
        return d


class GPUComponentConfiguration:
    def __init__(self, *, model: str):
        self.model = model

    @classmethod
    def from_dictionary(cls, dictionary: Mapping) -> GPUComponentConfiguration:
        model = dictionary["model"]
        return cls(model=model)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(model=self.model)
        return d


class StorageComponentConfiguration:
    def __init__(
        self,
        *,
        kind: str,
        model: str,
        name: str | None = None,
        auto_mount: bool = False,
        mount_point: str | None = None,
    ):
        self.kind = kind
        self.model = model
        self.name = name
        self.auto_mount = auto_mount
        self.mount_point = mount_point

    @classmethod
    def from_dictionary(cls, dictionary: Mapping) -> StorageComponentConfiguration:
        kwargs: MutableMapping = {}

        kind = dictionary["kind"]
        model = dictionary["model"]
        if kind == STORAGE:
            name = dictionary.get("name")
            kwargs.update(name=name)
            auto_mount = dictionary.get("auto_mount", False)
            kwargs.update(auto_mount=auto_mount)
        elif kind == NVME:
            mount_point = dictionary.get("mount_point")
            kwargs.update(mount_point=mount_point)

        return cls(kind=kind, model=model, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind, "model": self.model}
        if self.kind == STORAGE:
            if self.name:
                d.update(name=self.name)
            d.update(auto_mount=self.auto_mount)
        elif self.kind == NVME:
            if self.mount_point is not None:
                d.update(mount_point=self.mount_point)

        return d


class NICComponentConfiguration:
    def __init__(
        self,
        *,
        kind: str,
        model: str,
        name: str | None = None,
    ):
        self.kind = kind
        self.model = model
        self.name = name

    @classmethod
    def from_dictionary(cls, dictionary: Mapping | None) -> NICComponentConfiguration:
        dictionary = dictionary or {}
        kwargs: MutableMapping = {}

        kind = dictionary.get("kind", NIC_SHARED)
        model = dictionary.get("model", NIC_MODEL_CONNECTX_6)
        name = dictionary.get("name")
        kwargs.update(name=name)

        return cls(kind=kind, model=model, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {"kind": self.kind, "model": self.model}
        if self.name:
            d["name"] = self.name
        return d


class MachineConfiguration:
    def __init__(
        self,
        *,
        site: str = "",
        image: str = "",
        user: str = "",
        gpus: list[dict] | None = [],
        storage: list[dict] | None = [],
        roles=None,
        number: int = 1,
        flavour: str | None = None,
        flavour_desc: dict | None = None,
    ):
        self.site = site
        self.image = image
        self.user = user
        self.gpus: list[GPUComponentConfiguration] = []
        self.storage: list[StorageComponentConfiguration] = []
        self.roles = roles
        self.number = number

        if gpus:
            self.gpus = [GPUComponentConfiguration.from_dictionary(c) for c in gpus]
        if storage:
            self.storage = [
                StorageComponentConfiguration.from_dictionary(c) for c in storage
            ]

        # Internally we keep the flavour_desc as reference not a descriptor
        self.flavour = flavour
        self.flavour_desc = flavour_desc
        if flavour is None and flavour_desc is None:
            self.flavour, self.flavour_desc = DEFAULT_FLAVOUR
        elif self.flavour is None:
            self.flavour = "custom"
        elif self.flavour_desc is None:
            self.flavour_desc = FLAVOURS[self.flavour]

    @classmethod
    def from_dictionary(cls, dictionary: Mapping) -> MachineConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        kwargs.update(roles=roles)

        site = dictionary.get("site", "")
        kwargs.update(site=site)
        image = dictionary.get("image", "")
        kwargs.update(image=image)
        user = dictionary.get("user", "")
        kwargs.update(user=user)
        flavour = dictionary.get("flavour")
        if flavour is not None:
            kwargs.update(flavour=flavour)
        flavour_desc = dictionary.get("flavour_desc")
        if flavour_desc is not None:
            kwargs.update(flavour_desc=flavour_desc)
        gpus = dictionary.get("gpus")
        if gpus is not None:
            kwargs.update(gpus=gpus)
        storage = dictionary.get("storage")
        if storage is not None:
            kwargs.update(storage=storage)
        number = dictionary.get("number", 1)
        kwargs.update(number=number)

        return cls(**kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(
            site=self.site,
            image=self.image,
            user=self.user,
            roles=self.roles,
            number=self.number,
        )
        if self.flavour is not None and self.flavour != "custom":
            d["flavour"] = self.flavour
        if self.flavour_desc is not None and self.flavour == "custom":
            d["flavour_desc"] = self.flavour_desc
        if self.gpus:
            d["gpus"] = [g.to_dict() for g in self.gpus]
        if self.storage:
            d["storage"] = [s.to_dict() for s in self.storage]
        return d


def networks_from_dictionary(
    network,
) -> (
    Fabnetv4NetworkConfiguration
    | Fabnetv6NetworkConfiguration
    | Fabnetv4ExternalNetworkConfiguration
    | Fabnetv6ExternalNetworkConfiguration
    | L3VPNNetworkConfiguration
    | L2BridgeNetworkConfiguration
    | L2SiteToSiteNetworkConfiguration
    | L2PTPNetworkConfiguration
    | PortMirrorNetworkConfiguration
):
    network_kinds: dict[
        str,
        type[Fabnetv4NetworkConfiguration]
        | type[Fabnetv6NetworkConfiguration]
        | type[Fabnetv4ExternalNetworkConfiguration]
        | type[Fabnetv6ExternalNetworkConfiguration]
        | type[L3VPNNetworkConfiguration]
        | type[L2BridgeNetworkConfiguration]
        | type[L2SiteToSiteNetworkConfiguration]
        | type[L2PTPNetworkConfiguration]
        | type[L2PTPNetworkConfiguration]
        | type[PortMirrorNetworkConfiguration],
    ] = {
        FABNETV4: Fabnetv4NetworkConfiguration,
        FABNETV6: Fabnetv6NetworkConfiguration,
        FABNETV4EXT: Fabnetv4ExternalNetworkConfiguration,
        FABNETV6EXT: Fabnetv6ExternalNetworkConfiguration,
        L3VPN: L3VPNNetworkConfiguration,
        L2BRIDGE: L2BridgeNetworkConfiguration,
        L2STS: L2SiteToSiteNetworkConfiguration,
        L2PTP: L2PTPNetworkConfiguration,
        PORTMIRROR: PortMirrorNetworkConfiguration,
    }
    kind = network["kind"]
    return network_kinds[kind].from_dictionary(network)


class Fabnetv4NetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site: str,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = FABNETV4
        self.roles = roles
        self.name = name
        self.site = site
        self.cidr: IPv4Network | None = None
        self.ip_version = 4
        self.nic = nic

    @property
    def network(self) -> IPv4Network:
        return self.cidr or FABNET_V4_SUBNET

    @network.setter
    def network(self, value: IPv4Network):
        if not isinstance(value, IPv4Network):
            raise TypeError("Value must be of type IPv4Network")
        self.cidr = value

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Fabnetv4NetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site = dictionary["site"]
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)

        kwargs.update(name=name, nic=nic)

        return cls(roles=roles, site=site, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(kind=self.kind, roles=self.roles, site=self.site)
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class Fabnetv6NetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site: str,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = FABNETV6
        self.roles = roles
        self.name = name
        self.site = site
        self.cidr: IPv6Network | None = None
        self.ip_version = 6
        self.nic = nic
        self._allocated_ips: set[IPv6Interface] = set()

    @property
    def network(self) -> IPv6Network:
        return self.cidr or FABNET_V6_SUBNET

    @network.setter
    def network(self, value: IPv6Network):
        if not isinstance(value, IPv6Network):
            raise TypeError("Value must be of type IPv6Network")
        self.cidr = value

    def allocate_ip(self, ip: IPv6Interface) -> None:
        self._allocated_ips.add(ip)

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Fabnetv6NetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site = dictionary["site"]
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)
        kwargs.update(name=name, nic=nic)

        return cls(roles=roles, site=site, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(kind=self.kind, roles=self.roles, site=self.site)
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class Fabnetv4ExternalNetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site: str,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = FABNETV4EXT
        self.roles = roles
        self.name = name
        self.site = site
        self.cidr = FABNET_EXT_V4_SUBNET
        self.ip_version = 4
        self.nic = nic

    @property
    def network(self) -> IPv4Network:
        return self.cidr

    @network.setter
    def network(self, value: IPv4Network):
        if not isinstance(value, IPv4Network):
            raise TypeError("Value must be of type IPv4Network")
        self.cidr = value

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Fabnetv4ExternalNetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site = dictionary["site"]
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)
        kwargs.update(name=name, nic=nic)

        return cls(roles=roles, site=site, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(kind=self.kind, roles=self.roles, site=self.site, cidr=str(self.cidr))
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class Fabnetv6ExternalNetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site: str,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = FABNETV6EXT
        self.roles = roles
        self.name = name
        self.site = site
        self.cidr = FABNET_EXT_V6_SUBNET
        self.ip_version = 6
        self.nic = nic
        self._allocated_ips: set[IPv6Interface] = set()

    @property
    def network(self) -> IPv6Network:
        return self.cidr

    @network.setter
    def network(self, value: IPv6Network):
        if not isinstance(value, IPv6Network):
            raise TypeError("Value must be of type IPv6Network")
        self.cidr = value

    def allocate_ip(self, ip: IPv6Interface) -> None:
        self._allocated_ips.add(ip)

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> Fabnetv6ExternalNetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site = dictionary["site"]
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)
        kwargs.update(name=name, nic=nic)

        return cls(roles=roles, site=site, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(kind=self.kind, roles=self.roles, site=self.site, cidr=str(self.cidr))
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class L3VPNNetworkConfiguration:
    def __init__(self):
        self.kind = L3VPN
        raise NotImplementedError("FABRIC L3VPNNetworkConfiguration is not implemented")

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> L3VPNNetworkConfiguration:
        raise NotImplementedError("FABRIC L3VPNNetworkConfiguration is not implemented")

    def to_dict(self) -> dict:
        raise NotImplementedError("FABRIC L3VPNNetworkConfiguration is not implemented")


class L2BridgeNetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site: str,
        cidr: str | None = None,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = L2BRIDGE
        self.roles = roles
        self.name = name
        self.site = site
        self.cidr = ip_network(cidr) if cidr else next(V4_SUBNETS)
        self.ip_version = self.cidr.version if self.cidr else None
        self.nic = nic

    @property
    def network(self) -> IPv4Network | IPv6Network:
        return self.cidr

    @network.setter
    def network(self, value: IPv4Network | IPv6Network):
        if not isinstance(value, (IPv4Network, IPv6Network)):
            raise TypeError("Value must be of type IPv4Network or IPv6Network")
        self.cidr = value
        self.ip_version = self.cidr.version if self.cidr else None

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> L2BridgeNetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site = dictionary["site"]
        cidr = dictionary.get("cidr")
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)
        kwargs.update(name=name, cidr=cidr, nic=nic)

        return cls(roles=roles, site=site, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(kind=self.kind, roles=self.roles, site=self.site, cidr=str(self.cidr))
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class L2SiteToSiteNetworkConfiguration:
    def __init__(
        self,
        *,
        roles: list[str],
        name: str | None = None,
        site_1: str,
        site_2: str,
        cidr: str | None = None,
        nic: NICComponentConfiguration | None = None,
    ):
        self.kind = L2STS
        self.roles = roles
        self.name = name
        self.site_1 = site_1
        self.site_2 = site_2
        self.cidr = ip_network(cidr) if cidr else next(V4_SUBNETS)
        self.ip_version = self.cidr.version if self.cidr else None
        self.nic = nic

    @property
    def network(self) -> IPv4Network | IPv6Network:
        return self.cidr

    @network.setter
    def network(self, value: IPv4Network | IPv6Network):
        if not isinstance(value, (IPv4Network, IPv6Network)):
            raise TypeError("Value must be of type IPv4Network or IPv6Network")
        self.cidr = value
        self.ip_version = self.cidr.version if self.cidr else None

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> L2SiteToSiteNetworkConfiguration:
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        site_1 = dictionary["site_1"]
        site_2 = dictionary["site_2"]
        cidr = dictionary.get("cidr")
        name = dictionary.get("name")
        nic = dictionary.get("nic")
        nic = nic if nic is None else NICComponentConfiguration.from_dictionary(nic)
        kwargs.update(name=name, cidr=cidr, nic=nic)

        return cls(roles=roles, site_1=site_1, site_2=site_2, **kwargs)

    def to_dict(self) -> dict:
        d: dict = {}
        d.update(
            kind=self.kind,
            roles=self.roles,
            site_1=self.site_1,
            site_2=self.site_2,
            cidr=str(self.cidr),
        )
        if self.name:
            d["name"] = self.name
        if self.name:
            d["name"] = self.name
        if self.nic:
            d["nic"] = self.nic.to_dict()
        return d


class L2PTPNetworkConfiguration:
    def __init__(self):
        self.kind = L2PTP
        raise NotImplementedError("FABRIC L2PTPNetworkConfiguration is not implemented")

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> L2PTPNetworkConfiguration:
        raise NotImplementedError("FABRIC L2PTPNetworkConfiguration is not implemented")

    def to_dict(self) -> dict:
        raise NotImplementedError("FABRIC L2PTPNetworkConfiguration is not implemented")


class PortMirrorNetworkConfiguration:
    def __init__(self):
        self.kind = PORTMIRROR
        raise NotImplementedError(
            "FABRIC PortMirrorNetworkConfiguration is not implemented"
        )

    @classmethod
    def from_dictionary(cls, dictionary: dict) -> PortMirrorNetworkConfiguration:
        raise NotImplementedError(
            "FABRIC PortMirrorNetworkConfiguration is not implemented"
        )

    def to_dict(self) -> dict:
        raise NotImplementedError(
            "FABRIC PortMirrorNetworkConfiguration is not implemented"
        )
