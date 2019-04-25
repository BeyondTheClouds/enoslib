from .constants import FLAVOURS

QUEUE_TYPES = ["default", "testing", "production"]

STRATEGY = ["copy", "cow"]

SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"},
        "gateway": {"type": "string"},
        "gateway_user": {"type": "string"},
        "job_name": {"type": "string"},
        "queue": {"type": "string", "enum": QUEUE_TYPES},
        "walltime": {"type": "string"},
        "image": {"type": "string"},
        "strategy": {"type": "string", "enum": STRATEGY},
        "working_dir": {"type": "string"}
    },
    "additionalProperties": False,
    "required": ["resources"],
    "resources": {
        "title": "Resource",

        "type": "object",
        "properties": {
            "machines": {
                "type": "array",
                "items": {"$ref": "#/machine"}
            },
            "networks": {"type": "array", "items": {"type": "string"}}
        },
        "additionalProperties": False,
        "required": ["machines", "networks"],
    },

    "machine": {
        "title": "Compute",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "cluster": {"type": "string"},
            "number": {"type": "number"},
            "oneOf": [
                {"flavour": {"type": "string", "enum": list(FLAVOURS.keys())}},
                {"flavour_desc": {"$ref": "#/flavour_desc"}}
            ],

        },
        "required": ["roles", "cluster"]
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
