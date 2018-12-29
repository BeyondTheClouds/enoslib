from ..configuration import BaseConfiguration
from .constants import (DEFAULT_BACKEND, DEFAULT_BOX, DEFAULT_FLAVOUR,
                        DEFAULT_USER, FLAVOURS)
from .schema import SCHEMA


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        # top level atttributes
        self.resources = None
        self.backend = DEFAULT_BACKEND
        self.user = DEFAULT_USER
        self.box = DEFAULT_BOX

        self._machine_cls = MachineConfiguration
        self._network_cls = NetworkConfiguration

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        if validate:
            cls.validate(dictionnary)

        self = cls()
        _resources = dictionnary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.machines = [MachineConfiguration.from_dictionnary(m) for m in
                         _machines]
        self.networks = [NetworkConfiguration.from_dictionnary(n) for n in
                         _networks]
        for key in ["backend", "user", "box"]:
            value = dictionnary.get(key)
            if value is not None:
                setattr(self, key, value)

        self.finalize()
        return self

    def to_dict(self):
        d = {}
        d.update(backend=self.backend,
                 user=self.user,
                 box=self.box,
                 resources={
                     "machines": [m.to_dict() for m in self.machines],
                     "networks": [n.to_dict() for n in self.networks]
                 })
        return d


class MachineConfiguration:

    def __init__(self, *,
                 roles=None,
                 flavour=None,
                 flavour_desc=None,
                 number=1):

        self.roles = roles

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
    def from_dictionnary(cls, dictionnary):
        kwargs = {}
        roles = dictionnary["roles"]
        kwargs.update(roles=roles)

        flavour = dictionnary.get("flavour")
        if flavour is not None:
            kwargs.update(flavour=flavour)
        flavour_desc = dictionnary.get("flavour_desc")
        if flavour_desc is not None:
            kwargs.update(flavour_desc=flavour_desc)
        number = dictionnary.get("number")
        if number is not None:
            kwargs.update(number=number)

        return cls(**kwargs)

    def to_dict(self):
        d = {}
        d.update(roles=self.roles, flavour_desc=self.flavour_desc,
                 number=self.number)
        return d


class NetworkConfiguration:

    def __init__(self, *,
                 roles=None,
                 cidr=""):
        self.roles = roles
        self.cidr = cidr

    @classmethod
    def from_dictionnary(cls, dictionnary):
        kwargs = {}
        roles = dictionnary["roles"]
        cidr = dictionnary["cidr"]
        kwargs.update(roles=roles, cidr=cidr)

        return cls(**kwargs)

    def to_dict(self):
        d = {}
        d.update(roles=self.roles, cidr=self.cidr)
        return d
