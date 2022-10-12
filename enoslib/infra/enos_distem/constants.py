import os


PROVIDER_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

######
DEFAULT_ENV_NAME = "debian10-nfs"
DEFAULT_JOB_NAME = "EnOslib-distem"
DEFAULT_QUEUE = "default"
DEFAULT_WALLTIME = "02:00:00"
PLAYBOOK_PATH = os.path.join(PROVIDER_PATH, "ansible", "site.yml")


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

DEFAULT_FORCE_DEPLOY = False
PATH_DISTEMD_LOGS = "/var/log/distem"
FILE_DISTEMD_LOGS = os.path.join(PATH_DISTEMD_LOGS, "distemd-coord.log")
SUBNET_NAME = "enoslib_distem_network"
