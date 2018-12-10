import jsonschema


class BaseConfiguration:
    """Base class for all the provider configuration object.

    This should be used as it is.
    """

    # Setting this is defered to the inherited classes
    _SCHEMA = None

    def __init__(self):
        # A configuration has a least these two
        self.machines = []
        self.networks = []

        # Filling up with the right machine and network
        # constructor is deferred to the sub classes.
        self._machine_cls = str
        self._network_cls = str

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        """Alternative constructor. Build the configuration from a
        dictionnary."""
        pass

    @classmethod
    def from_settings(cls, **kwargs):
        """Alternative constructor. Build the configuration from a
        the kwargs."""
        self = cls()
        self.set(**kwargs)
        return self

    @classmethod
    def validate(cls, dictionnary):
        jsonschema.validate(dictionnary, cls._SCHEMA)

    def to_dict(self):
        return {}

    def finalize(self):
        d = self.to_dict()
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
        self.machines.append(self._machine_cls(*args, **kwargs))
        return self

    def add_network_conf(self, network):
        self.networks.append(network)
        return self

    def add_network(self, *args, **kwargs):
        self.networks.append(self._network_cls(*args, **kwargs))
        return self
