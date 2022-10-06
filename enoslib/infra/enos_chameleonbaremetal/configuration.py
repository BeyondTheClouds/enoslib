import enoslib.infra.enos_openstack.configuration as OSConfiguration

from .constants import (
    DEFAULT_CONFIGURE_NETWORK,
    DEFAULT_IMAGE,
    DEFAULT_NAMESERVERS,
    DEFAULT_NETWORK,
    DEFAULT_SUBNET,
    DEFAULT_USER,
)
from ..enos_chameleonkvm.schema import SCHEMA


class Configuration(OSConfiguration.Configuration):

    _SCHEMA = SCHEMA

    def __init__(self):
        super().__init__()
        # new keys
        self.lease_name = "enos-lease"
        self.walltime = "02:00:00"
        self.extra_ips = 0

        # overridden keys
        self.image = DEFAULT_IMAGE
        self.user = DEFAULT_USER
        self.configure_network = DEFAULT_CONFIGURE_NETWORK
        self.network = DEFAULT_NETWORK
        self.subnet = DEFAULT_SUBNET
        self.dns_nameservers = DEFAULT_NAMESERVERS

        self.gateway_user = self.user


class MachineConfiguration(OSConfiguration.MachineConfiguration):
    pass
