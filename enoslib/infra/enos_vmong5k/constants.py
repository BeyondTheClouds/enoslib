import os

from enoslib.infra.enos_g5k.constants import SLASH_22


DEFAULT_JOB_NAME = "EnOslib-vmong5k"
DEFAULT_QUEUE = "default"
DEFAULT_WALLTIME = "02:00:00"
# See  https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=10855
DEFAULT_IMAGE = "/grid5000/virt-images/debian11-x64-nfs.qcow2"
PROVIDER_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

PLAYBOOK_PATH = os.path.join(PROVIDER_PATH, "ansible", "site.yml")
DESTROY_PLAYBOOK_PATH = os.path.join(PROVIDER_PATH, "ansible", "destroy.yml")
LIBVIRT_DIR = "/var/lib/libvirt/images/enos_vmong5k"

#: Sizes of the machines available for the configuration
FLAVOURS = {
    "tiny": {"core": 1, "mem": 512},
    "small": {"core": 1, "mem": 1024},
    "medium": {"core": 2, "mem": 2048},
    "big": {"core": 3, "mem": 3072},
    "large": {"core": 4, "mem": 4096},
    "extra-large": {"core": 6, "mem": 6144},
}

DEFAULT_DOMAIN_TYPE = "kvm"

DEFAULT_FLAVOUR = "tiny", FLAVOURS["tiny"]

DEFAULT_NETWORKS = ["enos_network"]

DEFAULT_NUMBER = 1

DEFAULT_WORKING_DIR = "/tmp/enos_vmong5k"

DEFAULT_STRATEGY = "cow"

DEFAULT_SUBNET_TYPE = SLASH_22
