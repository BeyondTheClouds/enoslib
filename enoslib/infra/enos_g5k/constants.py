# -*- coding: utf-8 -*-
from pathlib import Path

JOB_TYPE_DEPLOY = "deploy"
DEFAULT_ENV_NAME = "debian9-x64-nfs"
DEFAULT_JOB_NAME = "EnOSlib"
DEFAULT_JOB_TYPE = JOB_TYPE_DEPLOY
DEFAULT_QUEUE = "default"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_NUMBER = 1
DEFAULT_SSH_KEYFILE = Path.home().joinpath(".ssh", "id_rsa.pub")

NAMESERVER = "dns.grid5000.fr"

NATURE_PROD = "prod"
SYNCHRONISATION_OFFSET = 60
G5KMACPREFIX = '00:16:3E'

# schema stuffs
KAVLAN = "kavlan"
KAVLAN_LOCAL = "kavlan-local"
KAVLAN_GLOBAL = "kavlan-global"
KAVLAN_TYPE = [KAVLAN, KAVLAN_LOCAL, KAVLAN_GLOBAL]

SLASH_22 = "slash_22"
SLASH_16 = "slash_16"
SUBNET_TYPES = [SLASH_16, SLASH_22]

PROD = "prod"

NETWORK_TYPES = [PROD] + KAVLAN_TYPE + SUBNET_TYPES
JOB_TYPES = ["deploy", "allow_classic_ssh"]
QUEUE_TYPES = ["default", "production", "testing"]