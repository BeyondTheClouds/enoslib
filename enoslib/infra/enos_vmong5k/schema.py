from jsonschema import Draft7Validator, FormatChecker

from .constants import (
    FLAVOURS,
    DEFAULT_WALLTIME,
    DEFAULT_JOB_NAME,
    DEFAULT_QUEUE,
    DEFAULT_STRATEGY,
    DEFAULT_SUBNET_TYPE,
    DEFAULT_WORKING_DIR,
    DEFAULT_DOMAIN_TYPE,
    DEFAULT_FLAVOUR,
    DEFAULT_NUMBER,
)
from enoslib.infra.enos_g5k.constants import QUEUE_TYPES, SUBNET_TYPES


STRATEGY = ["copy", "cow"]

SCHEMA = {
    "description": "VMonG5k schema.",
    "type": "object",
    "properties": {
        "enable_taktuk": {
            "description": "Use TakTuk to distribute the VM image",
            "type": "boolean",
        },
        "force_deploy": {
            "description": "Remove and restart all virtual machines",
            "type": "boolean",
        },
        "gateway": {
            "description": "Enable access to virtual machines from outside Grid'5000",
            "type": "boolean",
        },
        "job_name": {
            "description": f"Name of the job (default: {DEFAULT_JOB_NAME})",
            "type": "string",
        },
        "queue": {
            "description": f"Grid'5000 queue to use (default: {DEFAULT_QUEUE})",
            "type": "string",
            "enum": QUEUE_TYPES,
        },
        "walltime": {
            "description": f"Job duration (default: {DEFAULT_WALLTIME})",
            "type": "string",
        },
        "image": {
            "type": "string",
            "description": "Path to the base image on the reserved nodes",
        },
        "skip": {"description": "Skip this number of IPs", "type": "number"},
        "strategy": {
            "description": f"Base image strategy (default: {DEFAULT_STRATEGY})",
            "type": "string",
            "enum": STRATEGY,
        },
        "subnet_type": {
            "description": f"Subnet type to use (default: {DEFAULT_SUBNET_TYPE})",
            "type": "string",
            "enum": SUBNET_TYPES,
        },
        "working_dir": {
            "description": f"Remote working directory (default: {DEFAULT_WORKING_DIR})",
            "type": "string",
        },
        "domain_type": {
            "description": f"Domain type of the guest (default: {DEFAULT_DOMAIN_TYPE})",
            "type": "string",
        },
        "reservation": {
            "description": "Reservation date %Y-%m-%d %H:%M:%S (Paris Timezone)",
            "type": "string",
        },
        "resources": {
            "title": "VMonG5k Resource",
            "type": "object",
            "properties": {
                "machines": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/machine"},
                },
                "networks": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
            "required": ["machines", "networks"],
        },  # resources
    },  # properties
    "additionalProperties": False,
    "required": ["resources"],
    "definitions": {
        "machine": {
            "description": "VMonG5k Machine description",
            "title": "VMonG5k Compute",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "EnOSlib's roles",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "number": {
                    "description": f"Number of VMs (default: {DEFAULT_NUMBER})",
                    "type": "number",
                },
                "flavour": {
                    "description": f"Predefined flavour (default: {DEFAULT_FLAVOUR})",
                    "type": "string",
                    "enum": list(FLAVOURS.keys()),
                },
                "flavour_desc": {
                    "description": "Custom flavour description",
                    "$ref": "#/definitions/flavour_desc",
                },
                "cluster": {
                    "description": "Grid'5000 cluster for the undercloud",
                    "type": "string",
                },
                "undercloud": {
                    "description": "List of Host where the VM should be started.",
                    "type": "array",
                    "items": {"type": "object"},
                },
                "macs": {
                    "description": "List of MAC addresses to use for the vms",
                    "type": "array",
                    "items": {"type": "string", "format": "mac"},
                },
                "extra_devices": {
                    "description": "Libvirt XML description for extra devices.",
                    "type": "string",
                },
            },
            "required": ["roles"],
            "additionalProperties": False,
        },
        "flavour_desc": {
            "description": "Custom flavour for a virtual machine.",
            "title": "VMonG5k Flavour",
            "type": "object",
            "properties": {
                "core": {"type": "number", "description": "number of cores"},
                "mem": {"type": "number", "description": "memory size in MB"},
                "disk": {"type": "number", "description": "disk size in GB"},
            },
            "required": ["core", "mem"],
            "additionalProperties": False,
        },
    },  # definitions
}


VMonG5kFormatChecker = FormatChecker()


@VMonG5kFormatChecker.checks("mac")
def is_valid_mac(instance):
    from netaddr import EUI, mac_unix_expanded

    try:
        EUI(instance, dialect=mac_unix_expanded)
        return True
    except Exception:
        return False


def VMonG5kValidator(schema):
    return Draft7Validator(schema, format_checker=VMonG5kFormatChecker)
