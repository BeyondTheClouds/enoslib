from typing import Dict, Mapping, MutableMapping, Optional, Type

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_BACKEND,
    DEFAULT_BOX,
    DEFAULT_FLAVOUR,
    DEFAULT_NAME_PREFIX,
    DEFAULT_USER,
    FLAVOURS,
)
from .schema import SCHEMA


class Configuration(BaseConfiguration):
    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        # top level attributes
        self.resources = None
        self.backend = DEFAULT_BACKEND
        self.box = DEFAULT_BOX
        self.user = DEFAULT_USER
        self.name_prefix = DEFAULT_NAME_PREFIX
        self.config_extra = ""

        self._machine_cls: Type[MachineConfiguration] = MachineConfiguration
        self._network_cls: Type[NetworkConfiguration] = NetworkConfiguration

    @classmethod
    def from_dictionary(
        cls, dictionary: Mapping, validate: bool = True
    ) -> "Configuration":
        if validate:
            cls.validate(dictionary)

        self = cls()
        _resources = dictionary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.machines = [MachineConfiguration.from_dictionary(m) for m in _machines]
        self.networks = [NetworkConfiguration.from_dictionary(n) for n in _networks]

        for key in ["backend", "user", "box", "name_prefix", "config_extra"]:
            value = dictionary.get(key)
            if value is not None:
                setattr(self, key, value)

        for machine in self.machines:
            machine.backend = machine.backend or self.backend
            machine.box = machine.box or self.box
            machine.user = machine.user or self.user

        self.finalize()
        return self

    def to_dict(self) -> Dict:
        d: Dict = {}
        d.update(
            backend=self.backend,
            user=self.user,
            box=self.box,
            name_prefix=self.name_prefix,
            config_extra=self.config_extra,
            resources={
                "machines": [m.to_dict() for m in self.machines],
                "networks": [n.to_dict() for n in self.networks],
            },
        )
        return d


class MachineConfiguration:
    def __init__(
        self,
        *,
        roles=None,
        flavour: Optional[str] = None,
        flavour_desc: Optional[Dict] = None,
        number: int = 1,
        backend: str = DEFAULT_BACKEND,
        box: str = "",
        user: str = "",
        name_prefix: str = "",
        config_extra_vm: str = "",
    ):
        self.backend = backend
        self.box = box
        self.user = user
        self.name_prefix = name_prefix
        self.config_extra_vm = config_extra_vm
        self.roles = roles
        self.name_prefix = name_prefix

        # Internally we keep the flavour_desc as reference not a descriptor
        self.flavour = flavour
        self.flavour_desc = flavour_desc
        if flavour is None and flavour_desc is None:
            self.flavour, self.flavour_desc = DEFAULT_FLAVOUR
        if self.flavour is None:
            # self.flavour_desc is not None
            self.flavour = "custom"
        if self.flavour_desc is None:
            # self.flavour is not None
            self.flavour_desc = FLAVOURS[self.flavour]

        self.number = number

    @classmethod
    def from_dictionary(cls, dictionary: Mapping) -> "MachineConfiguration":
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        kwargs.update(roles=roles)

        flavour = dictionary.get("flavour")
        if flavour is not None:
            kwargs.update(flavour=flavour)
        flavour_desc = dictionary.get("flavour_desc")
        if flavour_desc is not None:
            kwargs.update(flavour_desc=flavour_desc)
        number = dictionary.get("number", 1)
        kwargs.update(number=number)
        backend = dictionary.get("backend", "")
        kwargs.update(backend=backend)
        box = dictionary.get("box", "")
        kwargs.update(box=box)
        user = dictionary.get("user", "")
        kwargs.update(user=user)
        name_prefix = dictionary.get("name_prefix", "")
        kwargs.update(name_prefix=name_prefix)
        config_extra_vm = dictionary.get("config_extra_vm", "")
        kwargs.update(config_extra_vm=config_extra_vm)

        return cls(**kwargs)

    def to_dict(self) -> Dict:
        d: Dict = {}
        d.update(
            roles=self.roles,
            flavour_desc=self.flavour_desc,
            number=self.number,
            box=self.box,
            backend=self.backend,
            user=self.user,
            name_prefix=self.name_prefix,
            config_extra_vm=self.config_extra_vm,
        )
        return d


class NetworkConfiguration:
    def __init__(self, *, roles=None, cidr=""):
        self.roles = roles
        self.cidr = cidr

    @classmethod
    def from_dictionary(cls, dictionary) -> "NetworkConfiguration":
        kwargs: MutableMapping = {}
        roles = dictionary["roles"]
        cidr = dictionary["cidr"]
        kwargs.update(roles=roles, cidr=cidr)

        return cls(**kwargs)

    def to_dict(self) -> Dict:
        d: Dict = {}
        d.update(roles=self.roles, cidr=self.cidr)
        return d
