import uuid

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_FLAVOUR,
    DEFAULT_JOB_NAME,
    DEFAULT_NETWORKS,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_WALLTIME,
    DEFAULT_FORCE_DEPLOY,
    FLAVOURS,
)
from enoslib.objects import Host
from .schema import SCHEMA


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.job_name = DEFAULT_JOB_NAME
        self.queue = DEFAULT_QUEUE
        self.walltime = DEFAULT_WALLTIME
        self.reservation = None
        ###
        self.force_deploy = DEFAULT_FORCE_DEPLOY

        self._machine_cls = MachineConfiguration
        self._network_cls = str

        self.networks = DEFAULT_NETWORKS

    @classmethod
    def from_dictionary(cls, dictionary, validate=True):
        if validate:
            cls.validate(dictionary)

        self = cls()
        for k in self.__dict__.keys():
            v = dictionary.get(k)
            if v is not None:
                setattr(self, k, v)

        _resources = dictionary["resources"]
        _machines = _resources["machines"]
        _networks = _resources["networks"]
        self.networks = _networks
        self.machines = [MachineConfiguration.from_dictionary(m) for m in _machines]

        self.finalize()
        return self

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in [
                "machines",
                "networks",
                "_machine_cls",
                "_network_cls",
            ]:
                continue
            d.update({k: v})

        d.update(
            resources={
                "machines": [m.to_dict() for m in self.machines],
                "networks": self.networks,
            }
        )
        return d


class MachineConfiguration:
    def __init__(
        self,
        *,
        roles=None,
        cluster=None,
        flavour=None,
        flavour_desc=None,
        number=DEFAULT_NUMBER,
        undercloud=None
    ):
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
        self.number = number
        self.cluster = cluster

        # a cookie to identify uniquely the group of machine this is used when
        # redistributing the vms to pms in the provider. I've the feeling that
        # this could be used to express some affinity between vms
        self.cookie = uuid.uuid4().hex

        #
        self.undercloud = undercloud if undercloud else []

    @classmethod
    def from_dictionary(cls, dictionary):
        kwargs = {}
        roles = dictionary["roles"]
        kwargs.update(roles=roles)

        flavour = dictionary.get("flavour")
        if flavour is not None:
            kwargs.update(flavour=flavour)
        flavour_desc = dictionary.get("flavour_desc")
        if flavour_desc is not None:
            kwargs.update(flavour_desc=flavour_desc)

        number = dictionary.get("number")
        if number is not None:
            kwargs.update(number=number)

        cluster = dictionary["cluster"]
        if cluster is not None:
            kwargs.update(cluster=cluster)

        undercloud = dictionary.get("undercloud")
        if undercloud is not None:
            undercloud = [Host.from_dict(h) for h in undercloud]
            kwargs.update(undercloud=undercloud)

        return cls(**kwargs)

    def to_dict(self):
        d = {}
        undercloud = self.undercloud
        if undercloud is not None:
            undercloud = [h.to_dict() for h in undercloud]
            d.update(undercloud=undercloud)
        cluster = self.cluster
        if cluster is not None:
            d.update(cluster=cluster)
        d.update(roles=self.roles, flavour_desc=self.flavour_desc, number=self.number)
        return d
