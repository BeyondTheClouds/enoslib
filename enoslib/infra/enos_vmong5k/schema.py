from .constants import FLAVOURS


from enoslib.infra.enos_g5k.constants import QUEUE_TYPES, SUBNET_TYPES


STRATEGY = ["copy", "cow"]

SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"},
        "enable_taktuk": {"type": "boolean"},
        "gateway": {"type": "string"},
        "gateway_user": {"type": "string"},
        "job_name": {"type": "string"},
        "queue": {"type": "string", "enum": QUEUE_TYPES},
        "walltime": {"type": "string"},
        "image": {"type": "string"},
        "strategy": {"type": "string", "enum": STRATEGY},
        "subnet_type": {"type": "string", "enum": SUBNET_TYPES},
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
            "number": {"type": "number"},
            "flavour": {"type": "string", "enum": list(FLAVOURS.keys())},
            "flavour_desc": {"$ref": "#/flavour_desc"},
            "cluster": {"type": "string"},
            "undercloud": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["roles"],
        "additionalProperties": False
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
