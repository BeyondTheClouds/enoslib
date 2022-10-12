from jsonschema import Draft7Validator, FormatChecker
from .error import EnosIotLabPhysicalNodesError, EnosIotlabStartTimeFormatError
from .error import EnosIotlabWalltimeFormatError
from .constants import (
    PROFILE_ARCHI_TYPES,
    RADIO_MODE_TYPES,
    CONSUMPTION_PERIOD_TYPES,
    CONSUMPTION_AVERAGE_TYPES,
    NETWORK_TYPES,
    DEFAULT_WALLTIME,
    DEFAULT_JOB_NAME,
    DEFAULT_NUMBER_BOARDS,
)

SCHEMA = {
    "type": "object",
    "title": "FIT/IoT-LAB configuration",
    "properties": {
        "job_name": {
            "description": f"Name of the job (default: {DEFAULT_JOB_NAME})",
            "type": "string",
        },
        "walltime": {
            "description": f"Job duration (default: {DEFAULT_WALLTIME})",
            "type": "string",
            "format": "walltime",
        },
        "start_time": {
            "description": "start time in YYYY-mm-dd HH:MM:SS format",
            "type": "string",
            "format": "start_time",
        },
        "resources": {
            "title": "Resource",
            "type": "object",
            "properties": {
                "machines": {
                    "oneOf": [
                        {
                            "type": "array",
                            "items": {"$ref": "#/definitions/physical_nodes"},
                            "minItems": 1,
                        },
                        {
                            "type": "array",
                            "items": {"$ref": "#/definitions/boards"},
                            "minItems": 1,
                        },
                    ]
                },
                "networks": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/network"},
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
            "required": ["machines"],
        },
        # Inspired on https://api.iot-lab.info/swagger.yaml#/components/schemas/Profile
        "monitoring": {
            "title": "FIT/IoT-LAB Monitoring profiles",
            "type": "object",
            "properties": {
                "profiles": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/profile"},
                    "minItems": 1,
                },
            },
            "additionalProperties": False,
            "required": ["profiles"],
        },
    },
    "additionalProperties": False,
    "required": ["resources"],
    "definitions": {
        "boards": {
            "title": "FIT/IoT-LAB boards selected by architecture",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "archi": {"description": "Architecture to use", "type": "string"},
                "site": {"description": "Site to use", "type": "string"},
                "number": {
                    "description": (
                        f"Number of boards (defaut: {DEFAULT_NUMBER_BOARDS})"
                    ),
                    "type": "number",
                },
                "image": {"description": "Firmware to use", "type": "string"},
                "profile": {"description": "profile name to use", "type": "string"},
            },
            "required": ["roles", "archi", "site"],
        },
        "physical_nodes": {
            "title": "FIT/IoT-LAB nodes selected by name",
            "type": "object",
            "properties": {
                "roles": {
                    "description": "The concrete resources will be assigned this role",
                    "type": "array",
                    "items": {"type": "string"},
                },
                "hostname": {
                    "description": "Exact name of physical nodes to use",
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "format": "hostname",
                },
                "image": {"description": "Firmware to use", "type": "string"},
                "profile": {"description": "profile name to use", "type": "string"},
            },
            "required": ["roles", "hostname"],
        },
        "network": {
            "title": "FIT/IoT-LAB Network",
            "type": "object",
            "properties": {
                "description": "Network to use",
                "id": {"type": "string"},
                "type": {"enum": NETWORK_TYPES},
                "roles": {"type": "array", "items": {"type": "string"}},
                "site": {"type": "string"},
            },
            "required": ["id", "type", "roles", "site"],
        },
        "profile": {
            "title": "FIT/IoT-LAB Radio and Consumption profiles",
            "type": "object",
            "properties": {
                "name": {"description": "The profile name", "type": "string"},
                "archi": {
                    "description": "Target architecture",
                    "type": "string",
                    "enum": PROFILE_ARCHI_TYPES,
                },
                "radio": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": RADIO_MODE_TYPES},
                        "num_per_channel": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 255,
                        },
                        "period": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "channels": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 11, "maximum": 26},
                        },
                    },
                    "additionalProperties": False,
                },
                "consumption": {
                    "type": "object",
                    "properties": {
                        "current": {"type": "boolean"},
                        "power": {"type": "boolean"},
                        "voltage": {"type": "boolean"},
                        "period": {"type": "integer", "enum": CONSUMPTION_PERIOD_TYPES},
                        "average": {
                            "type": "integer",
                            "enum": CONSUMPTION_AVERAGE_TYPES,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
            "required": ["name", "archi"],
        },
    },  # definitions
}

IotlabFormatChecker = FormatChecker()


@IotlabFormatChecker.checks("walltime", raises=EnosIotlabWalltimeFormatError)
def is_valid_walltime(instance):
    """Auxiliary function to check walltime format"""
    if not isinstance(instance, str):
        return False
    try:
        # HH:MM
        wt_str = instance.split(":")
        int(wt_str[0])
        int(wt_str[1])
        return True
    except Exception:
        raise EnosIotlabWalltimeFormatError()


@IotlabFormatChecker.checks("start_time", raises=EnosIotlabStartTimeFormatError)
def is_valid_start_time(instance):
    if not isinstance(instance, str):
        return False
    # YYYY-mm-dd HH:MM:SS
    from datetime import datetime

    try:
        datetime.strptime(instance, "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        raise EnosIotlabStartTimeFormatError()


@IotlabFormatChecker.checks("hostname", raises=EnosIotLabPhysicalNodesError)
def is_valid_physical_nodes(instance):
    if not isinstance(instance, list):
        return False
    archis = [machine.split("-")[0] for machine in instance]
    n_archis = len(set(archis))
    if n_archis != 1:
        raise EnosIotLabPhysicalNodesError(
            f"Found {n_archis} architecture(s) instead of 1"
        )
    return True


def IotlabValidator(schema):
    return Draft7Validator(schema, format_checker=IotlabFormatChecker)
