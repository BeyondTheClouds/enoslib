import warnings

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_JOB_NAME,
    DEFAULT_WALLTIME,
    DEFAULT_NUMBER,
)
from .schema import SCHEMA, ChameleonValidator


class Configuration(BaseConfiguration):
    """Global class for parsing Chameleon configuration"""

    _SCHEMA = SCHEMA
    _VALIDATOR_FUNC = ChameleonValidator

    def __init__(self):
        super().__init__()
        self.lease_name = DEFAULT_JOB_NAME
        self.rc_file = None
        self.walltime = DEFAULT_WALLTIME

        self._machine_cls = DeviceGroupConfiguration
        self._network_cls = NetworkConfiguration

    def add_machine(self, *args, **kwargs):
        # we need to discriminate between Device and DeviceCluster
        if kwargs.get("device_name") is not None:
            self.add_machine_conf(DeviceConfiguration(*args, **kwargs))
        elif kwargs.get("machine_name") is not None:
            self.add_machine_conf(DeviceClusterConfiguration(*args, **kwargs))
        else:
            raise ValueError(
                "Must be a device (device_name) or "
                "device cluster (machine_name) configuration"
            )
        return self

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

        self.machines = [DeviceGroupConfiguration.from_dictionary(m) for m in _machines]

        if "networks" in _resources:
            _networks = _resources["networks"]
            self.networks = [NetworkConfiguration.from_dictionary(n) for n in _networks]

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
                "networks": [n.to_dict() for n in self.networks],
            },
        )
        return d


class Container:
    """Base class for a container."""

    def __init__(
        self,
        name=None,
        image=None,
        exposed_ports=None,
        start=True,
        start_timeout=None,
        device_profiles=None,
        **kwargs,
    ):
        self.name = name
        self.image = image
        self.exposed_ports = exposed_ports
        self.start = start
        self.start_timeout = start_timeout
        self.device_profiles = device_profiles
        self.kwargs = kwargs

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
            d.update({k: v})
        return d


class DeviceGroupConfiguration:
    """Base class for a group of machines."""

    def __init__(
        self,
        *,
        roles=None,
        device_model=None,
        site=None,
        count=DEFAULT_NUMBER,
        container: Container = None,
    ):
        self.roles = roles
        self.device_model = device_model
        self.site = site
        self.count = count
        self.container = container

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
            if isinstance(v, Container):
                d.update({k: v.to_dict()})
            else:
                d.update({k: v})
        return d

    @classmethod
    def from_dictionnary(cls, *args, **kwargs):
        """Compatibility method (old method name that may still be used)"""
        warnings.warn(
            "from_dictionnary is deprecated in favor of from_dictionary",
            DeprecationWarning,
        )
        return cls.from_dictionary(*args, **kwargs)

    @classmethod
    def from_dictionary(cls, dictionary):
        roles = dictionary["roles"]
        device_model = dictionary.get("device_model")
        _container = dictionary["container"].copy()
        container = Container(
            name=_container.pop("name", None),
            image=_container.pop("image", None),
            exposed_ports=_container.pop("exposed_ports", None),
            start=_container.pop("start", None),
            start_timeout=_container.pop("start_timeout", None),
            device_profiles=_container.pop("device_profiles", None),
            **_container,
        )
        # device-cluster (machine_name) and
        # device (device_name) are no individually optional
        # nevertheless the schema validates that at least one is set
        device_name = dictionary.get("device_name")
        machine_name = dictionary.get("machine_name")

        if device_name is not None:
            return DeviceConfiguration(
                roles=roles,
                device_model=device_model,
                device_name=device_name,
                container=container,
            )

        if machine_name is not None:
            count = dictionary.get("count", DEFAULT_NUMBER)
            return DeviceClusterConfiguration(
                roles=roles,
                device_model=device_model,
                machine_name=machine_name,
                count=count,
                container=container,
            )

        raise ValueError(
            "Unable to build an instance "
            "DeviceConfiguration or DeviceClusterConfiguration"
        )


class DeviceClusterConfiguration(DeviceGroupConfiguration):
    def __init__(self, *, machine_name=None, **kwargs):
        super().__init__(**kwargs)
        self.machine_name = machine_name

    def to_dict(self):
        d = super().to_dict()
        d.update(machine_name=self.machine_name)
        return d


class DeviceConfiguration(DeviceGroupConfiguration):
    def __init__(self, *, device_name=None, **kwargs):
        super().__init__(**kwargs)
        self.device_name = device_name

    def to_dict(self):
        d = super().to_dict()
        d.update(device_name=self.device_name)
        return d


class NetworkConfiguration:
    """Class for network configuration"""

    def __init__(self, *, net_id=None, roles=None, net_type=None, site=None):
        self.roles = roles
        self.id = net_id
        self.roles = roles
        self.type = net_type
        self.site = site

    @classmethod
    def from_dictionary(cls, dictionary):
        my_id = dictionary["id"]
        my_type = dictionary["type"]
        roles = dictionary["roles"]
        site = dictionary["site"]

        return cls(net_id=my_id, roles=roles, net_type=my_type, site=site)

    def to_dict(self):
        d = {}
        d.update(id=self.id, type=self.type, roles=self.roles, site=self.site)
        return d
