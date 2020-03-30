SCHEMA = {
    "description": "Network constraint description",
    "type": "object",
    "properties": {
        "default_delay": {
            "type": "string",
            "description": "default delay to apply on all groups (e.g. 10ms)",
        },
        "default_rate": {
            "type": "string",
            "description": "default rate to apply on all groups (e.g. 1gbit)",
        },
        "default_loss": {
            "type": "number",
            "description": "default loss (percen) to apply on all groups (e.g. 0.1)",
        },
        "except": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exclude this groups",
        },
        "groups": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Include only this group",
        },
        "constraints": {"type": "array", "items": {"$ref": "#/constraint"}},
    },
    "required": ["default_delay", "default_rate"],
    "oneOf": [{"required": ["groups"]}, {"required": ["except"]}],
    "additionnalProperties": False,
    "constraint": {
        "type": "object",
        "description": {"Override constraints between specific groups"},
        "properties": {
            "src": {"type": "string", "description": "Source group"},
            "dst": {"type": "string", "description": "Destination group"},
            "delay": {"type": "string", "description": "Delay to apply"},
            "rate": {"type": "string", "description": "Rate to apply"},
            "loss": {"type": "number", "description": "Loss to apply (percentage)"},
            "network": {
                "type": "string",
                "description": "Network role to consider (default to all).",
            },
        },
        "additionnalProperties": False,
        "required": ["src", "dst"],
    },
}
