import warnings

from ..configuration import BaseConfiguration
from .constants import (
    DEFAULT_JOB_NAME,
    DEFAULT_WALLTIME,
    DEFAULT_NUMBER_BOARDS,
)
from .schema import SCHEMA, IotlabValidator


class Configuration(BaseConfiguration):
    """Global class for parsing IoT-LAB configuration"""

    _SCHEMA = SCHEMA
    _VALIDATOR_FUNC = IotlabValidator

    def __init__(self):
        super().__init__()
        self.job_name = DEFAULT_JOB_NAME
        self.walltime = DEFAULT_WALLTIME
        self.profiles = None
        self.start_time = None

        self._machine_cls = GroupConfiguration
        self._network_cls = NetworkConfiguration

    def add_machine(self, *args, **kwargs):
        # we need to discriminate between phys node and board
        if kwargs.get("archi") is not None:
            self.add_machine_conf(BoardConfiguration(*args, **kwargs))
        elif kwargs.get("hostname") is not None:
            self.add_machine_conf(PhysNodeConfiguration(*args, **kwargs))
        else:
            ValueError("Must be a physical node or board configuration")
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
        self.machines = [GroupConfiguration.from_dictionary(m) for m in _machines]

        if "networks" in _resources:
            _networks = _resources["networks"]
            self.networks = [NetworkConfiguration.from_dictionary(n) for n in _networks]

        if "monitoring" in dictionary:
            _monit = dictionary["monitoring"]
            _profiles = _monit["profiles"]
            self.profiles = [ProfileConfiguration.from_dictionary(p) for p in _profiles]

        self.finalize()
        return self

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in [
                "machines",
                "networks",
                "profiles",
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
        if self.profiles is not None:
            d.update(
                monitoring={
                    "profiles": [p.to_dict() for p in self.profiles],
                },
            )

        return d

    def add_profile(self, *args, **kwargs):
        if self.profiles is None:
            self.profiles = []
        self.profiles.append(ProfileConfiguration(*args, **kwargs))
        return self

    @property
    def walltime_s(self):
        """Returns the walltime of a configuration in seconds"""
        split = self.walltime.split(":")
        return int(split[0]) * 3600 + int(split[1]) * 60


class GroupConfiguration:
    """Base class for a group of machines"""

    def __init__(
        self,
        *,
        roles=None,
        image=None,
        profile=None,
    ):
        self.roles = roles
        self.image = image
        self.profile = profile

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
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
        image = dictionary.get("image")
        profile = dictionary.get("profile")
        # boards/archi and physical_nodes/hostname are no individually optional
        # nevertheless the schema validates that at least one is set
        archi = dictionary.get("archi")
        nodes = dictionary.get("hostname")

        if archi is not None and nodes is not None:
            raise ValueError(
                """The machines object must be uniform.
                            It contains both boards and physical nodes in this case.
                            Verify your config."""
            )

        if archi is not None:
            site = dictionary["site"]
            number = dictionary.get("number", DEFAULT_NUMBER_BOARDS)
            return BoardConfiguration(
                roles=roles,
                archi=archi,
                site=site,
                number=number,
                image=image,
                profile=profile,
            )

        if nodes is not None:
            return PhysNodeConfiguration(
                roles=roles,
                hostname=nodes,
                image=image,
                profile=profile,
            )
        raise ValueError("Unable to build an instance from board or node configuration")


class PhysNodeConfiguration(GroupConfiguration):
    """
    Represents a specific node.

    Selects the node with given address (hostname)
    """

    def __init__(self, *, hostname=None, **kwargs):
        super().__init__(**kwargs)
        self.hostname = hostname

    def to_dict(self):
        d = super().to_dict()
        d.update(hostname=self.hostname)
        return d


class BoardConfiguration(GroupConfiguration):
    """
    Generic node configuration.

    Any node, which  from testbed can be selected
    """

    def __init__(self, *, archi=None, site=None, number=None, **kwargs):
        super().__init__(**kwargs)
        self.archi = archi
        self.site = site
        self.number = number

    def to_dict(self):
        d = super().to_dict()
        for k, v in self.__dict__.items():
            if v is None:
                continue
            d.update({k: v})
        return d


class ProfileConfiguration:
    """Base for monitoring profiles"""

    def __init__(
        self,
        *,
        name=None,
        archi=None,
        consumption=None,
        radio=None,
    ):
        self.name = name
        self.archi = archi
        self.consumption = consumption
        self.radio = radio

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None or k in [
                "radio",
                "consumption",
            ]:
                continue
            d.update({k: v})
        if self.radio is not None:
            d.update(radio=self.radio.to_dict())

        if self.consumption is not None:
            d.update(consumption=self.consumption.to_dict())
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
        self = ProfileConfiguration(
            name=dictionary["name"],
            archi=dictionary["archi"],
        )
        if "radio" in dictionary:
            self.radio = RadioConfiguration.from_dictionary(dictionary["radio"])
        if "consumption" in dictionary:
            self.consumption = ConsumptionConfiguration.from_dictionary(
                dictionary["consumption"]
            )

        return self


class RadioConfiguration:
    """Defines a radio monitoring profile"""

    def __init__(
        self,
        *,
        mode=None,
        num_per_channel=None,
        period=None,
        channels=None,
    ):
        self.mode = mode
        self.num_per_channel = num_per_channel
        self.period = period
        self.channels = channels

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
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
        self = cls()

        for k in self.__dict__.keys():
            v = dictionary.get(k)
            if v is not None:
                setattr(self, k, v)

        return self


class ConsumptionConfiguration:
    """Defines a consumption monitoring profile"""

    def __init__(
        self,
        *,
        current=None,
        power=None,
        voltage=None,
        period=None,
        average=None,
    ):
        self.current = current
        self.power = power
        self.voltage = voltage
        self.period = period
        self.average = average

    def to_dict(self):
        d = {}
        for k, v in self.__dict__.items():
            if v is None:
                continue
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
        self = cls()

        for k in self.__dict__.keys():
            v = dictionary.get(k)
            if v is not None:
                setattr(self, k, v)

        return self


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
