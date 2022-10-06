import enoslib.infra.enos_openstack.configuration as OSConfiguration
from ..enos_chameleonkvm.schema import SCHEMA
from .constants import DEFAULT_IMAGE, DEFAULT_NAMESERVERS, DEFAULT_USER


class Configuration(OSConfiguration.Configuration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        self.image = DEFAULT_IMAGE
        self.dns_nameservers = DEFAULT_NAMESERVERS
        self.user = DEFAULT_USER
        self.gateway_user = self.user


class MachineConfiguration(OSConfiguration.MachineConfiguration):
    pass
