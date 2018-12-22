from ..schema import JSON_SCHEMA
from .constants import FLAVOURS, BACKENDS


SCHEMA = {
    "type": "object",
    "$schema": JSON_SCHEMA,
    "properties": {
        "backend": {"type": "string", "enum": BACKENDS},
        "box": {"type": "string"},
        "user": {"type": "string"},
        "resources": {"$ref": "#/resources"}
    },
    "additionalProperties": False,
    "required": ["resources"],

    "resources": {
        "title": "Resource",

        "type": "object",
        "properties": {
            "machines": {"type": "array", "items": {"$ref": "#/machine"}},
            "networks": {
                "type": "array",
                "items": {"$ref": "#/network"},
                "uniqueItems": True},
        },
        "additionalProperties": False,
        "required": ["machines", "networks"]
    },

    "machine": {
        "title": "Compute",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "number": {"type": "number"},
            "flavour": {"type": "string", "enum": list(FLAVOURS.keys())},
            "flavour_desc": {"$ref": "#/flavour_desc"}
        },
        "required": [
            "roles",
        ],
        "additionalProperties": False,
    },

    "network": {
        "type": "object",
        "properties": {
            "cidr": {"type": "string"},
            "roles": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
        "required": ["cidr", "roles"]
    },

    "flavour_desc": {
        "title": "Flavour",
        "type": "object",
        "properties": {
            "core": {"type": "number"},
            "mem": {"type": "number"}
        },
        "required": ["core", "mem"],
        "additionalProperties": False
    }
}
