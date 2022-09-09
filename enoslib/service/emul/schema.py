from jsonschema import Draft7Validator, FormatChecker


CONSTRAINT_SCHEMA = {
    "type": "object",
    "description": {"Override constraints between specific groups"},
    "properties": {
        "src": {"type": "string", "description": "Source group"},
        "dst": {"type": "string", "description": "Destination group"},
        "delay": {
            "type": "string",
            "description": "Delay to apply [ms]",
            "format": "delay",
        },
        "rate": {
            "type": "string",
            "description": "Rate to apply [kbit, mbit, gbit]",
            "format": "rate",
        },
        "loss": {
            "type": ["string", "null"],
            "description": "Loss to apply (percentage)",
            "format": "loss",
        },
        "network": {
            "type": "string",
            "description": "Network role to consider (default to all).",
        },
    },
    "additionnalProperties": False,
    "required": ["src", "dst"],
}

CONCRETE_CONSTRAINT_SCHEMA = {
    "type": "object",
    "properties": {
        "device": {"type": "string"},
        "target": {"type": "string", "format": "ipv4"},
        "delay": {"type": "string", "description": "Delay to apply", "format": "delay"},
        "rate": {"type": "string", "description": "Rate to apply", "format": "rate"},
        "loss": {
            "type": ["string", "null"],
            "description": "Loss to apply (percentage)",
            "format": "loss",
        },
    },
    "additionnalProperties": False,
}

SCHEMA = {
    "description": "Network constraint description",
    "type": "object",
    "properties": {
        "default_delay": {
            "type": "string",
            "description": "default delay to apply on all groups (e.g. 10ms)",
            "format": "delay",
        },
        "default_rate": {
            "type": "string",
            "description": "default rate to apply on all groups (e.g. 1gbit)",
            "format": "rate",
        },
        "default_loss": {
            "type": "str",
            "description": "default loss (percent) to apply on all groups (e.g. 0.1%)",
            "format": "loss",
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
        "network": {
            "type": "string",
            "description": "Apply constraints on this network only (default to all)",
        },
        "constraints": {"type": "array", "items": {"$ref": "#/constraint"}},
    },
    "required": ["default_delay", "default_rate"],
    #    "oneOf": [{"required": ["groups"]}, {"required": ["except"]}],
    "additionnalProperties": False,
    "constraint": CONSTRAINT_SCHEMA,
}

HTBFormatChecker = FormatChecker()


@HTBFormatChecker.checks("delay")
def is_valid_delay(instance):
    """Something that ends with ms."""
    if not isinstance(instance, str):
        return False
    if not instance.endswith("ms"):
        return False
    return True


@HTBFormatChecker.checks("rate")
def is_valid_rate(instance):
    """Something that ends with kbit, mbit or gbit."""
    if not isinstance(instance, str):
        return False
    if (
        not instance.endswith("gbit")
        and not instance.endswith("mbit")
        and not instance.endswith("kbit")
    ):
        return False
    return True


@HTBFormatChecker.checks("loss")
def is_valid_loss(instance):
    """semantic:
    None: don't set any netem loss rule
    x%: set a rule with x% loss
    """
    if instance is None:
        return True
    # whatever
    if not isinstance(instance, str):
        return False
    # str
    import re

    return re.match(r"\d*.?\d*%", str(instance))


@HTBFormatChecker.checks("ipv4")
def is_valid_ipv4(instance):
    import ipaddress

    try:
        # accept ipv4 and ipv6
        ipaddress.ip_interface(instance)
        return True
    except ipaddress.AddressValueError:
        return False


HTBValidator = Draft7Validator(SCHEMA, format_checker=HTBFormatChecker)

HTBConstraintValidator = Draft7Validator(
    CONSTRAINT_SCHEMA, format_checker=HTBFormatChecker
)

HTBConcreteConstraintValidator = Draft7Validator(
    CONCRETE_CONSTRAINT_SCHEMA, format_checker=HTBFormatChecker
)
