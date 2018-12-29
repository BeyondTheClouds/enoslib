SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"},
    },
    "additionalProperties": True,
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
            "address": {"type": "string"},
            "alias": {"type": "string"},
            "user": {"type":  "string"},
            "keyfile": {"type": "string"},
            "port": {"type": "number"},
            "extra": {"type": "object"}
        },
        "required": ["roles", "address"]
    },

    "network": {
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            # TODO(msimonin): validate the ip schema
            "start": {"type": "string"},
            "end": {"type": "string"},
            "cidr": {"type": "string"},
            "gateway": {"type": "string"},
            "dns": {"type": "string"}
        },
        "required": ["roles", "start", "end", "cidr", "gateway", "dns"]
    }
}
