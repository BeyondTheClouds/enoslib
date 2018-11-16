from ..configuration import BaseConfiguration
from .constants import (DEFAULT_FLAVOUR, DEFAULT_IMAGE, DEFAULT_JOB_NAME,
                        DEFAULT_NETWORKS, DEFAULT_NUMBER, DEFAULT_QUEUE,
                        DEFAULT_WALLTIME, FLAVOURS)
from .schema import SCHEMA

import uuid


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.job_name = DEFAULT_JOB_NAME
        self.queue = DEFAULT_QUEUE
        self.walltime = DEFAULT_WALLTIME
        self.image = DEFAULT_IMAGE

        self._machine_cls = MachineConfiguration
        self._network_cls = str

        self.networks = DEFAULT_NETWORKS

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        if validate:
            cls.validate(dictionnary)

        self = cls()
        for k in self.__dict__.keys():
            v = dictionnary.get(k)
            if v is not None:
                setattr(self, k, v)

        _resources = dictionnary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.networks = [NetworkConfiguration.from_dictionnary(n) for n in
                         _networks]
        self.machines = [MachineConfiguration.from_dictionnary(m) for m in
                         _machines]

        self.finalize()
        return self

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in ["machines", "networks", "_machine_cls",
                                  "_network_cls"]:
                continue
            d.update({k: v})

        d.update(resources={
            "machines": [m.to_dict() for m in self.machines],
            "networks": self.networks
        })
        return d


class MachineConfiguration:

    def __init__(self, *,
               roles=None,
               cluster=None,
               flavour=None,
               number=DEFAULT_NUMBER):
        self.roles = roles

        if flavour is None:
            self.flavour = DEFAULT_FLAVOUR
        if isinstance(flavour, dict):
            self.flavour = flavour
        elif isinstance(flavour, str):
            self.flavour = FLAVOURS[flavour]
        else:
            self.flavour = DEFAULT_FLAVOUR

        self.number = number
        self.cluster = cluster

        # a cookie to identify uniquely the group of machine this is used when
        # redistributing the vms to pms in the provider. I've the feeling that
        # this could be used to express some affinity between vms
        self.cookie = uuid.uuid4().hex

    @classmethod
    def from_dictionnary(cls, dictionnary):
        kwargs = {}
        roles = dictionnary["roles"]
        kwargs.update(roles=roles)
        flavour = dictionnary.get("flavour")
        if flavour is not None:
            # The flavour name is used in the dictionnary
            # This makes a diff with the constructor where
            # A dict describing the flavour is given
            kwargs.update(flavour=FLAVOURS[flavour])
        number = dictionnary.get("number")
        if number is not None:
            kwargs.update(number=number)

        cluster = dictionnary["cluster"]
        if cluster is not None:
            kwargs.update(cluster=cluster)

        return cls(**kwargs)

    def to_dict(self):
        d = {}
        d.update(roles=self.roles, flavour=self.flavour, number=self.number,
                 cluster=self.cluster)
        return d
