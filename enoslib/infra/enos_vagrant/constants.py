# Box
DEFAULT_BOX = "generic/debian11"

# Backends
BACKEND_VIRTUALBOX = "virtualbox"
BACKEND_LIBVIRT = "libvirt"
BACKENDS = [BACKEND_LIBVIRT, BACKEND_VIRTUALBOX]

DEFAULT_BACKEND = BACKEND_LIBVIRT

# User
DEFAULT_USER = "root"

#: The default configuration of the vagrant provider
DEFAULT_CONFIG = {"backend": DEFAULT_BACKEND, "box": DEFAULT_BOX, "user": DEFAULT_USER}

#: Sizes of the machines available for the configuration
FLAVOURS = {
    "tiny": {"core": 1, "mem": 512},
    "small": {"core": 1, "mem": 1024},
    "medium": {"core": 2, "mem": 2048},
    "big": {"core": 3, "mem": 3072},
    "large": {"core": 4, "mem": 4096},
    "extra-large": {"core": 6, "mem": 6144},
}

DEFAULT_FLAVOUR = "tiny", FLAVOURS["tiny"]


DEFAULT_NETWORKS = ["enos_network"]


DEFAULT_NUMBER = 1


DEFAULT_NAME_PREFIX = "enos"
