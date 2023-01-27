import re
from typing import Dict, Iterable

from jsonschema import Draft7Validator, FormatChecker

from ..utils import merge_dict
from .constants import (
    DEFAULT_JOB_NAME,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_WALLTIME,
    JOB_TYPES_REGEXP,
    NETWORK_TYPES,
    QUEUE_TYPES,
)
from .error import (
    EnosG5kInvalidJobTypesError,
    EnosG5kReservationDateFormatError,
    EnosG5kWalltimeFormatError,
)

SCHEMA_USER = {
    "type": "object",
    "title": "Grid5000 Configuration Schema",
    "properties": {
        "dhcp": {
            "description": "Run dhcp client automatically on kavlan networks "
            "(default: True)",
            "type": "boolean",
        },
        "force_deploy": {
            "description": "Force systematic redeployment on nodes (deploy only) "
            "(default: False)",
            "type": "boolean",
        },
        "env_name": {
            "description": "The kadeploy3 environment to use (deploy only)",
            "type": "string",
        },
        "env_version": {
            "description": "Kadeploy3 env version to use (deploy only, optional)",
            "type": "integer",
            "minimum": 2016011914,
            "exclusiveMinimum": True,
        },
        "job_name": {
            "description": f"Name of the job (default: {DEFAULT_JOB_NAME})",
            "type": "string",
        },
        "job_type": {
            "description": "OAR job type (default: []).",
            "anyOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string"}},
            ],
            "format": "job_type",
        },
        "key": {
            # Note: We don't use the constants.DEFAULT_SSH_KEYFILE
            # Because at build time on the CI this will be set to /root/.ssh
            # which doesn't correspond to what the user will have most likely
            "description": "SSH public key to use (default: ~/.ssh/.id_rsa.pub)",
            "type": "string",
        },
        "monitor": {
            "description": "Activate on demand metrics (e.g ``prom_.*``)",
            "type": "string",
        },
        "oargrid_jobids": {
            "description": "Reload from existing job ids",
            "type": "array",
            "items": {"$ref": "#/definitions/jobids"},
        },
        "project": {
            "description": "Project / team to use",
            "type": "string",
        },
        "queue": {
            "description": f"OAR queue to use (default: {DEFAULT_QUEUE})",
            "type": "string",
            "enum": QUEUE_TYPES,
        },
        "reservation": {
            "description": "reservation date in YYYY-mm-dd HH:MM:SS format",
            "type": "string",
            "format": "reservation",
        },
        "walltime": {
            "description": f"Job duration (default: {DEFAULT_WALLTIME})",
            "type": "string",
            "format": "walltime",
        },
        "resources": {
            "title": "Grid'5000 Resources",
            "type": "object",
            "properties": {
                "machines": {
                    "description": "Description of the servers to reserve",
                    "type": "array",
                    "items": {
                        "oneOf": [
                            {"$ref": "#/definitions/cluster"},
                            {"$ref": "#/definitions/servers"},
                        ]
                    },
                },
                "networks": {
                    "description": "Description of the networks to reserve",
                    "type": "array",
                    "items": {"$ref": "#/definitions/network"},
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
            "required": ["machines"],
        },  # resources
    },  # properties
    "additionalProperties": False,
    "required": ["resources"],
    "definitions": {
        "jobids": {
            "description": "List of tuple (site, jobid) used to reload the jobs from",
            "title": "Grid5000 JobIds",
            "type": "array",
            "items": {"type": "string"},
        },
        "cluster": {
            "description": "Describe a group of machine based on a cluster name",
            "title": "Grid5000 ComputeCluster",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "cluster": {"description": "Which cluster to use", "type": "string"},
                "nodes": {
                    "description": f"Number of nodes (default: {DEFAULT_NUMBER})",
                    "type": "number",
                },
                "min": {
                    "description": "Minimal number of nodes to get (default to nodes)",
                    "type": "number",
                },
                "reservable_disks": {
                    "description": "Request access to reservable disks on nodes",
                    "type": "boolean",
                },
                "primary_network": {
                    "description": "Network(id) to use on the primary NIC",
                    "type": "string",
                },
                "secondary_networks": {
                    "description": "Additional networks(ids) to assign",
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
            },
            "required": ["roles", "cluster"],
        },
        "servers": {
            "description": "Description of a specific list of servers to get",
            "title": "Grid5000 ComputeServers",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "servers": {
                    "description": "List of names (e.g [chetemi-1.lille.grid5000.fr]) ",
                    "type": "array",
                    "items": {"type": "string", "format": "hostname"},
                    "minItems": 1,
                },
                "min": {
                    "description": "Minimal number of nodes to get (default to nodes)",
                    "type": "number",
                },
                "reservable_disks": {
                    "description": "Request access to reservable disks on nodes",
                    "type": "boolean",
                },
                "primary_network": {
                    "description": "Network to use on this NIC",
                    "type": "string",
                },
                "secondary_networks": {
                    "description": "List of the network to use on the other NICs",
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
            },
            "required": ["roles", "servers"],
        },
        "network": {
            "title": "Grid5000 Network",
            "type": "object",
            "properties": {
                "id": {
                    "description": "Id used to identify network in machines",
                    "type": "string",
                },
                "type": {
                    "description": "Type of network to use supported by Grid'5000",
                    "enum": NETWORK_TYPES,
                },
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "site": {
                    "description": "On which site to reserve the network",
                    "type": "string",
                },
            },
            "required": ["id", "type", "roles", "site"],
        },
    },
}


SCHEMA_USER_DIFF = {
    "resources": {
        "required": ["machines", "networks"],
    },
    "cluster": {
        "required": ["roles", "cluster", "primary_network"],
    },
    "servers": {
        "required": ["roles", "servers", "primary_network"],
    },
}


SCHEMA_INTERNAL = merge_dict(SCHEMA_USER, SCHEMA_USER_DIFF)

"""
Additional notes

Supported network types are

    - kavlan
    - kavlan-local
    - kavlan-global
    - prod
    - slash_22 (subnet reservation)
    - slash_18 (subnet reservation)

Machines must use at least one network of type prod or kavlan*. Subnets are
optional and must not be linked to any interfaces as they are a way to
claim extra ips and corresponding macs. In this case the returned network
attributes `start` and `end` corresponds to the first and last mapping of
(ip, mac).

If a key ``oargrid_jobid`` is found, the resources will be reloaded from
the corresponding oargrid job. In this case what is described under the
``resources`` key mut be compatible with the job content.

If the keys ``oar_jobid`` and ``oar_site`` are found, the resources will be
reloaded from the corresponding oar job. In this case what is described
under the ``resources`` key mut be compatible with the job content.

"""
G5kFormatChecker = FormatChecker()


@G5kFormatChecker.checks("hostname")
def is_valid_hostname(instance) -> bool:
    if not isinstance(instance, str):
        return False
    # cluster-n.site.grid5000.fr
    pattern = r"\w+-\d+.\w+.grid5000.fr"
    return re.match(pattern, instance) is not None


@G5kFormatChecker.checks("job_type", raises=EnosG5kInvalidJobTypesError)
def is_valid_job_type(instance: Iterable) -> bool:
    if isinstance(instance, str):
        instance = [instance]

    invalid = []
    for job_type in instance:
        validation = [re.match(r, job_type) for r in JOB_TYPES_REGEXP]
        if not any(validation):
            invalid.append(job_type)

    if invalid:
        raise EnosG5kInvalidJobTypesError(invalid)

    return True


@G5kFormatChecker.checks("walltime", raises=EnosG5kWalltimeFormatError)
def is_valid_walltime(instance) -> bool:
    if not isinstance(instance, str):
        return False
    # HH:MM:SS
    from datetime import datetime

    try:
        [hours, minutes_seconds] = instance.split(":", 1)
        int(hours)
        datetime.strptime(minutes_seconds, "%M:%S")
        return True
    except ValueError as err:
        raise EnosG5kWalltimeFormatError() from err


@G5kFormatChecker.checks("reservation", raises=EnosG5kReservationDateFormatError)
def is_valid_reservation_date(instance) -> bool:
    if not isinstance(instance, str):
        return False
    # YYYY-MM-DD hh:mm:ss
    from datetime import datetime

    try:
        datetime.strptime(instance, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError as err:
        raise EnosG5kReservationDateFormatError() from err


def G5kValidator(schema: Dict):
    return Draft7Validator(schema, format_checker=G5kFormatChecker)
