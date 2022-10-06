from pathlib import Path

JOB_TYPE_DEPLOY = "deploy"
DEFAULT_JOB_NAME = "EnOSlib"
DEFAULT_QUEUE = "default"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_NUMBER = 1
DEFAULT_SSH_KEYFILE = str(Path.home() / ".ssh" / "id_rsa.pub")

# Unused except for backwards compatibility (kavlan),
# users now need to always specify the env_name themselves.
DEFAULT_ENV_NAME_COMPAT = "debian11-nfs"

NAMESERVER = "dns.grid5000.fr"

NATURE_PROD = "prod"
SYNCHRONISATION_OFFSET = 60
SYNCHRONISATION_INTERVAL = 300
G5KMACPREFIX = "00:16:3E"

# Exposed to the user when auto-creating a prod network
NETWORK_ROLE_PROD = "prod"

# schema stuffs
KAVLAN = "kavlan"
KAVLAN_LOCAL = "kavlan-local"
KAVLAN_LOCAL_IDS = ["1", "2", "3"]
KAVLAN_IDS = ["4", "5", "6", "7", "8"]
KAVLAN_GLOBAL = "kavlan-global"
KAVLAN_TYPE = [KAVLAN, KAVLAN_LOCAL, KAVLAN_GLOBAL]

SLASH_22 = "slash_22"
SLASH_16 = "slash_16"
SUBNET_TYPES = [SLASH_16, SLASH_22]

PROD = "prod"
PROD_VLAN_ID = "DEFAULT"

NETWORK_TYPES = [PROD] + KAVLAN_TYPE + SUBNET_TYPES
JOB_TYPES = ["deploy", "allow_classic_ssh", "exotic"]
QUEUE_TYPES = ["default", "production", "testing", "besteffort"]


MAX_DEPLOY = 3
