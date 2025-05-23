from typing import Dict, Mapping

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_ALLOCATION_POOL,
    DEFAULT_CONFIGURE_NETWORK,
    DEFAULT_DNS_NAMESERVERS,
    DEFAULT_GATEWAY,
    DEFAULT_NETWORK,
    DEFAULT_PREFIX,
    DEFAULT_SUBNET,
)
from .schema import SCHEMA


class Configuration(BaseConfiguration):
    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.key_name = None
        self.image = None
        self.user = None
        self.rc_file = None

        self.allocation_pool = DEFAULT_ALLOCATION_POOL
        self.configure_network = DEFAULT_CONFIGURE_NETWORK
        self.dns_nameservers = DEFAULT_DNS_NAMESERVERS
        self.gateway = DEFAULT_GATEWAY
        self.gateway_user = self.user
        self.network = DEFAULT_NETWORK
        self.subnet = DEFAULT_SUBNET
        self.prefix = DEFAULT_PREFIX

        self._machine_cls = MachineConfiguration
        self._network_cls = str

    @classmethod
    def from_dictionary(
        cls, dictionary: Mapping, validate: bool = True
    ) -> "Configuration":
        if validate:
            cls.validate(dictionary)

        self = cls()
        for k in self.__dict__:
            v = dictionary.get(k)
            if v is not None:
                setattr(self, k, v)
        _machines = dictionary["resources"]["machines"]
        _networks = dictionary["resources"]["networks"]
        self.machines = [MachineConfiguration.from_dictionary(m) for m in _machines]
        self.networks = _networks

        for machine in self.machines:
            machine.image = machine.image or self.image
            machine.user = machine.user or self.user

        self.finalize()
        return self

    def to_dict(self) -> Dict:
        d: Dict = {}
        d.update(
            key_name=self.key_name,
            image=self.image,
            user=self.user,
            rc_file=self.rc_file,
            resources={
                "machines": [m.to_dict() for m in self.machines],
                "networks": self.networks,
            },
        )
        return d


class MachineConfiguration:
    def __init__(self, *, image=None, user=None, roles=None, flavour=None, number=None):
        self.image = image
        self.user = user
        self.roles = roles
        self.flavour = flavour
        self.number = number

    @classmethod
    def from_dictionary(cls, dictionary: Mapping) -> "MachineConfiguration":
        image = dictionary.get("image", None)
        user = dictionary.get("user", None)
        roles = dictionary["roles"]
        flavour = dictionary["flavour"]
        number = dictionary["number"]
        return cls(image=image, user=user, roles=roles, flavour=flavour, number=number)

    def to_dict(self) -> Dict:
        d: Dict = {}
        d.update(
            roles=self.roles,
            flavour=self.flavour,
            number=self.number,
        )
        if self.image is not None:
            d["image"] = self.image
        if self.user is not None:
            d["user"] = self.user

        return d
