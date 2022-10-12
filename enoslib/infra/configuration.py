import logging
import json
from typing import Callable, Dict, Optional, Any
import warnings

import jsonschema

from enoslib.html import html_from_dict, repr_html_check

logger = logging.getLogger(__name__)
STATIC_FILES = "html/style.css"


class BaseConfiguration:
    """Base class for all the provider configuration object.

    This should be used as it is.
    """

    # Setting this is deferred to the inherited classes
    _SCHEMA: Optional[Dict[Any, Any]] = None
    _VALIDATOR_FUNC: Optional[Callable[[Dict], Any]] = None

    def __init__(self):
        # A configuration has the least these two
        self.machines = []
        self.networks = []

        # Filling up with the right machine and network
        # constructor is deferred to the sub-classes.
        self._machine_cls = str
        self._network_cls = str

    @classmethod
    def from_dictionary(cls, dictionary, validate=True):
        """Alternative constructor. Build the configuration from a
        dictionary."""
        pass

    @classmethod
    def from_dictionnary(cls, *args, **kwargs):
        """Compatibility method (old method name that may still be used)"""
        warnings.warn(
            "from_dictionnary is deprecated in favor of from_dictionary",
            DeprecationWarning,
        )
        return cls.from_dictionary(*args, **kwargs)

    @classmethod
    def from_settings(cls, **kwargs):
        """Alternative constructor. Build the configuration from
        the kwargs."""
        self = cls()
        self.set(**kwargs)
        return self

    @classmethod
    def validate(cls, dictionary, schema=None):
        if schema is None:
            schema = cls._SCHEMA
        if cls._VALIDATOR_FUNC is None:
            jsonschema.validate(dictionary, schema)
        else:
            # pylint: disable-next=not-callable
            cls._VALIDATOR_FUNC(schema).validate(dictionary)

    def to_dict(self):
        return {}

    def finalize(self):
        d = self.to_dict()
        import json

        logger.debug(json.dumps(d, indent=4))
        self.validate(d)
        return self

    def set(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

    def add_machine_conf(self, machine):
        self.machines.append(machine)
        return self

    def add_machine(self, *args, **kwargs):
        self.machines.append(self._machine_cls(**kwargs))
        return self

    def add_network_conf(self, network):
        self.networks.append(network)
        return self

    def add_network(self, *args, **kwargs):
        self.networks.append(self._network_cls(*args, **kwargs))
        return self

    def __repr__(self):
        r = f"Conf@{hex(id(self))}\n"
        r += json.dumps(self.to_dict(), indent=4)
        return r

    @repr_html_check
    def _repr_html_(self) -> str:
        class_name = f"{str(self.__class__)}@{hex(id(self))}"
        return html_from_dict(class_name, self.to_dict(), content_only=False)
