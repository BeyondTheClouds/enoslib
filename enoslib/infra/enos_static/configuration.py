from ..configuration import BaseConfiguration
from .schema import SCHEMA


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self._network_cls = NetworkConfiguration
        self._machine_cls = MachineConfiguration

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

        self.finalize()
        return self

    def to_dict(self):
        return {
            "resources": {
                "machines": [m.to_dict() for m in self.machines],
                "networks": [n.to_dict() for n in self.networks]
            }
        }


class MachineConfiguration:

    def __init__(self, *,
                 address=None,
                 roles=None,
                 alias=None,
                 user=None,
                 keyfile=None,
                 port=None,
                 extra=None):
        self.address = address
        self.roles = roles
        self.alias = alias
        self.user = user
        self.keyfile = keyfile
        self.port = port
        self.extra = extra if extra is not None else {}

    @classmethod
    def from_dictionnary(cls, dictionnary):

        return cls(address=dictionnary["address"],
                   roles=dictionnary["roles"],
                   alias=dictionnary.get("alias"),
                   user=dictionnary.get("user"),
                   keyfile=dictionnary.get("keyfile"),
                   port=dictionnary.get("port"),
                   extra=dictionnary.get("extra"))

    def to_dict(self):
        d = {}
        d.update(address=self.address, roles=self.roles)
        if self.alias:
            d.update(alias=self.alias)
        if self.user:
            d.update(user=self.user)
        if self.keyfile:
            d.update(keyfile=self.keyfile)
        if self.port:
            d.update(port=self.port)
        if self.extra:
            d.update(extra=self.extra)

        return d


class NetworkConfiguration:

    def __init__(self, *,
                 roles=None,
                 start=None,
                 end=None,
                 cidr=None,
                 gateway=None,
                 dns=None):
        self.roles = roles
        self.cidr = cidr
        self.gateway = gateway
        self.start = start
        self.end = end
        self.dns = dns

    @classmethod
    def from_dictionnary(cls, dictionnary):

        return cls(roles=dictionnary["roles"],
                   start=dictionnary["start"],
                   end=dictionnary["end"],
                   cidr=dictionnary["cidr"],
                   gateway=dictionnary["gateway"],
                   dns=dictionnary["dns"])

    def to_dict(self):
        d = {}
        d.update(roles=self.roles,
                 start=self.start,
                 end=self.end,
                 cidr=self.cidr,
                 gateway=self.gateway,
                 dns=self.dns)
        return d
