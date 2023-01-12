# NOTE(msimonin): build the subnet following the good rules
# https://www.chameleoncloud.org/docs/bare-metal-user-guide/network-isolation-bare-metal/
# Some defaults
SUBNET_CIDR = "10.87.23.0/24"

GLANCE_VERSION = "2"
NEUTRON_VERSION = "2"
NOVA_VERSION = "2.1"

DEFAULT_PREFIX = "enos"
# These are private resources
NETWORK_NAME = f"{DEFAULT_PREFIX}-network"
ROUTER_NAME = f"{DEFAULT_PREFIX}-router"
SECGROUP_NAME = f"{DEFAULT_PREFIX}-secgroup"
SUBNET_NAME = f"{DEFAULT_PREFIX}-subnet"


DEFAULT_CONFIGURE_NETWORK = True
DEFAULT_NETWORK = {"name": NETWORK_NAME}
DEFAULT_SUBNET = {"name": SUBNET_NAME, "cidr": SUBNET_CIDR}
DEFAULT_DNS_NAMESERVERS = ["8.8.8.8", "8.8.4.4"]
DEFAULT_ALLOCATION_POOL = {"start": "10.87.23.10", "end": "10.87.23.100"}
DEFAULT_GATEWAY = True
