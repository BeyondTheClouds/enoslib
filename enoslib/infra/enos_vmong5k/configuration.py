from typing import Iterable, Optional
import uuid
from enoslib.infra.enos_g5k.g5k_api_utils import get_cluster_site

from enoslib.objects import Host
from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_DOMAIN_TYPE,
    DEFAULT_FLAVOUR,
    DEFAULT_IMAGE,
    DEFAULT_JOB_NAME,
    DEFAULT_NETWORKS,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_STRATEGY,
    DEFAULT_SUBNET_TYPE,
    DEFAULT_WALLTIME,
    DEFAULT_WORKING_DIR,
    FLAVOURS,
)
from .schema import SCHEMA, VMonG5kValidator


class Configuration(BaseConfiguration):

    _SCHEMA = SCHEMA
    _VALIDATOR_FUNC = VMonG5kValidator

    def __init__(self):
        super().__init__()
        self.domain_type = DEFAULT_DOMAIN_TYPE
        self.enable_taktuk = False
        self.force_deploy = False
        self.gateway = False
        self.job_name = DEFAULT_JOB_NAME
        self.queue = DEFAULT_QUEUE
        self.reservation = None
        self.walltime = DEFAULT_WALLTIME
        self.image = DEFAULT_IMAGE
        self.skip = 0
        self.strategy = DEFAULT_STRATEGY
        self.subnet_type = DEFAULT_SUBNET_TYPE
        self.working_dir = DEFAULT_WORKING_DIR

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
        undercloud: Optional[Iterable[Host]] = None,
        macs: Optional[Iterable[str]] = None,
        extra_devices=""
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
        self.cluster = cluster

        # a cookie to identify uniquely the group of machine this is used when
        # redistributing the vms to pms in the provider. I've the feeling that
        # this could be used to express some affinity between vms
        self.cookie = uuid.uuid4().hex

        # Which physical machine will be used to host the vms of this group
        self.undercloud = undercloud if undercloud else []
        # Pool of mac to use to configure the virtual machines
        # TODO(msimonin): Check that we have enough macs for the number of
        # wanted VMs
        self.macs = macs if macs else []
        self.extra_devices = extra_devices

    @property
    def site(self):
        return get_cluster_site(self.cluster)

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

        macs = dictionary.get("macs")
        if macs is not None:
            kwargs.update(macs=macs)

        extra_devices = dictionary.get("extra_devices")
        if extra_devices is not None:
            kwargs.update(extra_devices=extra_devices)

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
        d.update(
            roles=self.roles,
            flavour_desc=self.flavour_desc,
            number=self.number,
            extra_devices=self.extra_devices,
            macs=self.macs,
        )
        return d
