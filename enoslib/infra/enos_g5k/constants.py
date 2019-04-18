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