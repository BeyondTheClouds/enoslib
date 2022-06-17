# -*- coding: utf-8 -*-
DEFAULT_JOB_NAME = "EnOSlib"
DEFAULT_WALLTIME = "02:00:00"
DEFAULT_NUMBER = 1
DEFAULT_CONFIGURE_NETWORK = False
DEFAULT_NETWORK = {"name": "containernet1"}

PROD = "prod"
NETWORK_TYPES = [PROD]

ROLES = "roles"
ROLES_SEPARATOR = "---"
ROLES_CONTAINER_ATTR = "labels"

OS_WHITE_LIST_DEBUG = ["OS_AUTH_TYPE", "OS_AUTH_URL", "OS_REGION_NAME"]