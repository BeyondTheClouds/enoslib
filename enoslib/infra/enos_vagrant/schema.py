from ..schema import JSON_SCHEMA
from .constants import BACKENDS, DEFAULT_BACKEND, DEFAULT_BOX, DEFAULT_USER, FLAVOURS


SCHEMA = {
    "type": "object",
    "title": "Vagrant Configuration Schema",
    "$schema": JSON_SCHEMA,
    "properties": {
        "backend": {
            "descripton": f"VM hypervisor to use (default: {DEFAULT_BACKEND})",
            "type": "string",
            "enum": BACKENDS,
        },
        "box": {
            "description": f"base image to use (default: {DEFAULT_BOX})",
            "type": "string",
        },
        "user": {
            "description": f"SSH user to use (default: {DEFAULT_USER})",
            "type": "string",
        },
        "name_prefix": {
            "description": "Prepend this prefix to box names",
            "type": "string",
        },
        "config_extra": {
            "description": "Extra config to pass (in vargrant DSL",
            "type": "string",
        },
        "resources": {
            "title": "Vagrant Resource",
            "type": "object",
            "properties": {
                "networks": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/network"},
                    "uniqueItems": True,
                },
                "machines": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/machine"},
                },
            },
            "additionalProperties": False,
            "required": ["machines", "networks"],
        },  # resources
    },  # properties
    "additionalProperties": False,
    "required": ["resources"],
    "definitions": {
        "network": {
            "title": "Vagrant Network",
            "$$target": "#/definitions/network",
            "type": "object",
            "properties": {
                "cidr": {"type": "string"},
                "roles": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
            "required": ["cidr", "roles"],
        },
        "machine": {
            "title": "Vagrant Compute",
            "$$target": "#/definitions/machine",
            "type": "object",
            "properties": {
                "roles": {"type": "array", "items": {"type": "string"}},
                "number": {"type": "number"},
                "name_prefix": {"type": "string"},
                "flavour": {"type": "string", "enum": list(FLAVOURS.keys())},
                "flavour_desc": {"$ref": "#/definitions/flavour_desc"},
            },
            "required": ["roles"],
            "oneOf": [{"required": ["flavour"]}, {"required": ["flavour_desc"]}],
            "additionalProperties": False,
        },
        "flavour_desc": {
            "title": "Vagrant Flavour",
            "type": "object",
            "properties": {"core": {"type": "number"}, "mem": {"type": "number"}},
            "required": ["core", "mem"],
            "additionalProperties": False,
        },
    },
}
