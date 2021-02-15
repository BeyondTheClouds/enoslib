# -*- coding: utf-8 -*-
from jsonschema import Draft7Validator, FormatChecker
from .error import EnosIotlabWalltimeFormatError
from .constants import (
    PROFILE_ARCHI_TYPES,
    RADIO_MODE_TYPES,
    CONSUMPTION_PERIOD_TYPES,
    CONSUMPTION_AVERAGE_TYPES,
    NETWORK_TYPES,
)

SCHEMA = {
    "type": "object",
    "title": "FIT/IoT-LAB configuration",
    "properties": {
        "job_name": {"type": "string"},
        "walltime": {
            "type": "string",
            "format": "walltime",
            "description": "walltime in HH:MM format",
        },
        "resources": {"$ref": "#/resources"},
        "monitoring": {"$ref": "#/monitoring"},
    },
    "additionalProperties": False,
    "required": ["resources"],
    "resources": {
        "title": "Resource",
        "type": "object",
        "properties": {
            "machines": {
                "oneOf": [
                    {"type": "array",
                    "items": {"$ref": "#physical_nodes"},
                    "minItems": 1,
                    },
                    {"type": "array",
                    "items": {"$ref": "#boards"},
                    "minItems": 1,
                    },
                ]
            },
            "networks": {
                "type": "array",
                "items": {"$ref": "#/network"},
                "uniqueItems": True,
            },
        },
        "additionalProperties": False,
        "required": ["machines"],
    },
    "boards": {
        "title": "FIT/IoT-LAB boards selected by architecture",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "archi": {"type": "string"},
            "site": {"type": "string"},
            "number": {"type": "number"},
            "image": {"type": "string"},
            "profile": {"type": "string"},
        },
        "required": ["roles", "archi", "site"],
    },
    "physical_nodes": {
        "title": "FIT/IoT-LAB nodes selected by name",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "hostname": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "image": {"type": "string"},
            "profile": {"type": "string"},
        },
        "required": ["roles", "hostname"],
    },
    "network": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"enum": NETWORK_TYPES},
            "roles": {"type": "array", "items": {"type": "string"}},
            "site": {"type": "string"},
        },
        "required": ["id", "type", "roles", "site"],
    },
    # Inspired on https://api.iot-lab.info/swagger.yaml#/components/schemas/Profile
    "monitoring": {
        "title": "Monitoring profiles",
        "type": "object",
        "properties": {
            "profiles": {"type": "array", "items": {"$ref": "#profile"}, "minItems": 1},
        },
        "additionalProperties": False,
        "required": ["profiles"],
    },
    "profile": {
        "title": "Radio and Consumption profiles",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "archi": {"type": "string", "enum": PROFILE_ARCHI_TYPES},
            "radio": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": RADIO_MODE_TYPES},
                    "num_per_channel": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 255
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
                    "average": {"type": "integer", "enum": CONSUMPTION_AVERAGE_TYPES},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
        "required": ["name", "archi"],
    }
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


IotlabValidator = Draft7Validator(SCHEMA, format_checker=IotlabFormatChecker)
