
# Box
DEFAULT_BOX = "generic/debian9"

# Backends
BACKEND_VIRTUALBOX = "virtualbox"
BACKEND_LIBVIRT = "libvirt"
BACKENDS = [BACKEND_LIBVIRT, BACKEND_VIRTUALBOX]

DEFAULT_BACKEND = BACKEND_LIBVIRT

# User
DEFAULT_USER = "root"

#: The default configuration of the vagrant provider
DEFAULT_CONFIG = {
    "backend": DEFAULT_BACKEND,
    "box": DEFAULT_BOX,
    "user": DEFAULT_USER,
}

#: Sizes of the machines available for the configuration
FLAVOURS = {
    "tiny": {
        "cpu": 1,
        "mem": 512
    },
    "small": {
        "cpu": 1,
        "mem": 1024
    },
    "medium": {
        "cpu": 2,
        "mem": 2048
    },
    "big": {
        "cpu": 3,
        "mem": 3072,
    },
    "large": {
        "cpu": 4,
        "mem": 4096
    },
    "extra-large": {
        "cpu": 6,
        "mem": 6144
    }
}

DEFAULT_FLAVOUR = FLAVOURS["tiny"]


DEFAULT_NETWORKS = ["enos_network"]


DEFAULT_NUMBER = 1
