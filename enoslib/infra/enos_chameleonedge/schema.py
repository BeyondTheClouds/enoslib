from jsonschema import Draft7Validator, FormatChecker
from .error import EnosChameleonWalltimeFormatError


SCHEMA = {
    "type": "object",
    "title": "Chameleon configuration",
    "properties": {
        "lease_name": {"type": "string"},
        "rc_file": {"type": "string"},
        "walltime": {
            "type": "string",
            "format": "walltime",
            "description": "walltime in HH:MM format",
        },
        "resources": {"$ref": "#/resources"},
    },
    "additionalProperties": True,
    "required": ["resources", "rc_file"],
    "resources": {
        "title": "Resource",
        "type": "object",
        "properties": {
            "machines": {
                "type": "array",
                "items": {"oneOf": [{"$ref": "#deviceCluster"}, {"$ref": "#device"}]},
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
    "deviceCluster": {
        "title": "DeviceCluster: CHI@Edge devices selected by board name",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "machine_name": {"type": "string"},
            "device_model": {"type": "string"},
            "count": {"type": "number"},
            "container": {"$ref": "#/container"},
        },
        "required": ["roles", "machine_name", "count"],
    },
    "device": {
        "title": "Device: CHI@Edge device selected by device name (e.g. iot-jetson04)",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
            "device_name": {"type": "string"},
            "device_model": {"type": "string"},
            "container": {"$ref": "#/container"},
        },
        "required": ["roles", "device_name"],
    },
    "container": {
        "title": "Chameleon Docker Container",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "image": {"type": "string"},
            "exposed_ports": {"type": "array", "items": {"type": "string"}},
            "start": {"type": "boolean"},
            "start_timeout": {"type": "number"},
            "device_profiles": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "image"],
    },
    "network": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"enum": ["prod"]},
            "roles": {"type": "array", "items": {"type": "string"}},
            "site": {"type": "string"},
        },
        "required": ["id", "type", "roles", "site"],
    },
}


ChameleonFormatChecker = FormatChecker()


@ChameleonFormatChecker.checks("walltime", raises=EnosChameleonWalltimeFormatError)
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
        raise EnosChameleonWalltimeFormatError()


def ChameleonValidator(schema):
    return Draft7Validator(schema, format_checker=ChameleonFormatChecker)
