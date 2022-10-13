from .constants import FLAVOURS


from .constants import (
    DEFAULT_JOB_NAME,
    DEFAULT_WALLTIME,
    DEFAULT_ENV_NAME,
    DEFAULT_NUMBER,
    DEFAULT_QUEUE,
    DEFAULT_FLAVOUR,
)
from enoslib.infra.enos_g5k.constants import QUEUE_TYPES


STRATEGY = ["copy", "cow"]

SCHEMA = {
    "type": "object",
    "properties": {
        "job_name": {
            "description": f"The job name (default: {DEFAULT_JOB_NAME})",
            "type": "string",
        },
        "queue": {
            "description": f"Queue to use (default: {DEFAULT_QUEUE})",
            "type": "string",
            "enum": QUEUE_TYPES,
        },
        "walltime": {
            "description": f"Job duration (default: {DEFAULT_WALLTIME})",
            "type": "string",
        },
        "image": {
            "description": f"Default base image to use (default: {DEFAULT_ENV_NAME})",
            "type": "string",
        },
        "reservation": {
            "description": "reservation date in YYYY-mm-dd HH:MM:SS format",
            "type": "string",
            "format": "reservation",
        },
        "force_deploy": {
            "description": "Clean the existing containers beforehand (default: False)",
            "type": "boolean",
        },
        "resources": {
            "title": "Distem Resource",
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
        },
    },
    "additionalProperties": False,
    "required": ["resources", "image"],
    "definitions": {
        "machine": {
            "title": "Distem Compute",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "number": {
                    "description": f"Number of containers (default: {DEFAULT_NUMBER})",
                    "type": "number",
                },
                "flavour": {
                    "description": f"Predefined flavour (default: {DEFAULT_FLAVOUR})",
                    "type": "string",
                    "enum": list(FLAVOURS.keys()),
                },
                "flavour_desc": {"$ref": "#/definitions/flavour_desc"},
                "cluster": {"type": "string"},
                "undercloud": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["roles"],
            "oneOf": [{"required": ["flavour"]}, {"required": ["flavour_desc"]}],
            "additionalProperties": False,
        },
        "flavour_desc": {
            "title": "Distem Flavour",
            "description": "Custom flavour/size for your container",
            "type": "object",
            "properties": {"core": {"type": "number"}, "mem": {"type": "number"}},
            "required": ["core", "mem"],
            "additionalProperties": False,
        },
    },
}
