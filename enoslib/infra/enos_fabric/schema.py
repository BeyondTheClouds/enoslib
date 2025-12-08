from ipaddress import IPv4Network, IPv6Network, ip_network

from jsonschema import Draft7Validator, FormatChecker

from enoslib.errors import EnosError

from ..schema import JSON_SCHEMA
from .constants import (  # L3VPN,; L2PTP, PORTMIRROR,
    DEFAULT_IMAGE,
    DEFAULT_NAME_PREFIX,
    DEFAULT_SITE,
    DEFAULT_USER,
    DEFAULT_WALLTIME,
    FABNETV4,
    FABNETV4EXT,
    FABNETV6,
    FABNETV6EXT,
    FLAVOURS,
    GPU_MODEL_A30,
    GPU_MODEL_A40,
    GPU_MODEL_RTX_6000,
    GPU_MODEL_TESLA_T4,
    L2BRIDGE,
    L2STS,
    NIC_MODEL_CONNECTX_5,
    NIC_MODEL_CONNECTX_6,
    NIC_SHARED,
    NIC_SMART,
    NVME,
    STORAGE,
    STORAGE_MODEL_NAS,
    STORAGE_MODEL_P4510,
)

SCHEMA = {
    "type": "object",
    "title": "FABRIC Configuration Schema",
    "$schema": JSON_SCHEMA,
    "properties": {
        "rc_file": {"type": "string"},
        "walltime": {
            "type": "string",
            "format": "walltime",
            "description": f"walltime in HH:MM format. Default to {DEFAULT_WALLTIME}",
        },
        "site": {
            "description": "Name of the site to deploy the node on. "
            f"Default to a {DEFAULT_SITE}.",
            "type": "string",
        },
        "image": {
            "description": f"Base image to use (default: {DEFAULT_IMAGE})",
            "type": "string",
        },
        "user": {
            "description": f"SSH user to use (default: {DEFAULT_USER})",
            "type": "string",
        },
        "name_prefix": {
            "description": "Prefix to use for the name of the nodes. "
            f"Default: {DEFAULT_NAME_PREFIX}",
            "type": "string",
        },
        "resources": {
            "title": "FABRIC Resource",
            "type": "object",
            "properties": {
                "networks": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/network"},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "machines": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/machine"},
                },
            },
            "additionalProperties": False,
            "required": ["machines", "networks"],
        },
    },
    "additionalProperties": False,
    "required": ["rc_file", "resources"],
    "definitions": {
        "network": {
            "title": "FABRIC Network",
            "$$target": "#/definitions/network",
            "type": "object",
            "properties": {
                "roles": {"type": "array", "items": {"type": "string"}},
                "name": {"type": "string", "minLength": 2},
            },
            "oneOf": [
                {"$ref": "#/definitions/fabnetv4"},
                {"$ref": "#/definitions/fabnetv6"},
                {"$ref": "#/definitions/fabnetv4ext"},
                {"$ref": "#/definitions/fabnetv6ext"},
                # {"$ref": "#/definitions/l3vpn"},
                {"$ref": "#/definitions/l2bridge"},
                {"$ref": "#/definitions/l2sts"},
                # {"$ref": "#/definitions/l2ptp"},
                # {"$ref": "#/definitions/portmirror"},
            ],
            "required": ["roles"],
        },
        "fabnetv4": {
            "title": "FABRIC Fabnetv4 Network",
            "$$target": "#/definitions/fabnetv4",
            "type": "object",
            "properties": {
                "kind": {"const": FABNETV4},
                "site": {"type": "string", "minLength": 3},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site"],
        },
        "fabnetv6": {
            "title": "FABRIC Fabnetv6 Network",
            "$$target": "#/definitions/fabnetv6",
            "type": "object",
            "properties": {
                "kind": {"const": FABNETV6},
                "site": {"type": "string", "minLength": 3},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site"],
        },
        "fabnetv4ext": {
            "title": "FABRIC Fabnetv4Ext Network",
            "$$target": "#/definitions/fabnetv4ext",
            "type": "object",
            "properties": {
                "kind": {"const": FABNETV4EXT},
                "site": {"type": "string", "minLength": 3},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site"],
        },
        "fabnetv6ext": {
            "title": "FABRIC Fabnetv6Ext Network",
            "$$target": "#/definitions/fabnetv6ext",
            "type": "object",
            "properties": {
                "kind": {"const": FABNETV6EXT},
                "site": {"type": "string", "minLength": 3},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site"],
        },
        # "l3vpn": {
        #     "title": "FABRIC L3VPN Network",
        #     "$$target": "#/definitions/l3vpn",
        #     "type": "object",
        #     "properties": {
        #         "kind": {"const": L3VPN},
        #         "nic": {"$ref": "#/definitions/nic"},
        #     },
        #     "required": ["kind"],
        # },
        "l2bridge": {
            "title": "FABRIC L2Bridge Network",
            "$$target": "#/definitions/l2bridge",
            "type": "object",
            "properties": {
                "kind": {"const": L2BRIDGE},
                "site": {"type": "string", "minLength": 3},
                "cidr": {"type": "string", "format": "ip"},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site"],
        },
        "l2sts": {
            "title": "FABRIC L2STS Network",
            "$$target": "#/definitions/l2sts",
            "type": "object",
            "properties": {
                "kind": {"const": L2STS},
                "site_1": {"type": "string", "minLength": 3},
                "site_2": {"type": "string", "minLength": 3},
                "cidr": {"type": "string", "format": "ip"},
                "nic": {"$ref": "#/definitions/nic"},
            },
            "required": ["kind", "site_1", "site_2"],
        },
        # "l2ptp": {
        #     "title": "FABRIC L2PTP Network",
        #     "$$target": "#/definitions/l2ptp",
        #     "type": "object",
        #     "properties": {
        #         "kind": {"const": L2PTP},
        #         "cidr": {"type": "string"},
        #         "nic": {"$ref": "#/definitions/nic"},
        #     },
        #     "required": ["kind"],
        # },
        # "portmirror": {
        #     "title": "FABRIC PortMirror Network",
        #     "$$target": "#/definitions/portmirror",
        #     "type": "object",
        #     "properties": {
        #         "kind": {"const": PORTMIRROR},
        #         "nic": {"$ref": "#/definitions/nic"},
        #     },
        #     "required": ["kind"],
        # },
        "machine": {
            "title": "FABRIC Compute",
            "$$target": "#/definitions/machine",
            "type": "object",
            "properties": {
                "site": {
                    "description": "Name of the site to deploy the node on. "
                    f"Default to {DEFAULT_SITE}.",
                    "type": "string",
                },
                "image": {
                    "description": "Base image to use",
                    "type": "string",
                },
                "user": {
                    "description": "SSH user to use",
                    "type": "string",
                },
                "gpus": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/gpu"},
                    "minItems": 1,
                },
                "storage": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/storage"},
                    "minItems": 1,
                },
                "roles": {"type": "array", "items": {"type": "string"}},
                "number": {"type": "number"},
                "flavour": {"type": "string", "enum": list(FLAVOURS.keys())},
                "flavour_desc": {"$ref": "#/definitions/flavour_desc"},
            },
            "required": ["roles"],
            "oneOf": [{"required": ["flavour"]}, {"required": ["flavour_desc"]}],
            "additionalProperties": False,
        },
        "gpu": {
            "title": "FABRIC GPU Component",
            "$$target": "#/definitions/gpu",
            "type": "object",
            "properties": {
                "model": {
                    "enum": [
                        GPU_MODEL_TESLA_T4,
                        GPU_MODEL_RTX_6000,
                        GPU_MODEL_A30,
                        GPU_MODEL_A40,
                    ]
                }
            },
            "required": ["model"],
        },
        "storage": {
            "title": "FABRIC Storage Component",
            "$$target": "#/definitions/component",
            "type": "object",
            "oneOf": [
                {
                    "properties": {
                        "kind": {"const": NVME},
                        "model": {"enum": [STORAGE_MODEL_P4510]},
                        "mount_point": {"type": "string", "minLength": 2},
                    }
                },
                {
                    "properties": {
                        "name": {"type": "string", "minLength": 2},
                        "kind": {"const": STORAGE},
                        "model": {"enum": [STORAGE_MODEL_NAS]},
                        "auto_mount": {"type": "boolean", "default": False},
                    },
                    "required": ["name"],
                },
            ],
            "required": ["kind", "model"],
        },
        "nic": {
            "title": "FABRIC NIC Component",
            "$$target": "#/definitions/nic",
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 2},
            },
            "oneOf": [
                {
                    "properties": {
                        "kind": {"const": NIC_SHARED},
                        "model": {"enum": [NIC_MODEL_CONNECTX_6]},
                    }
                },
                {
                    "properties": {
                        "kind": {"const": NIC_SMART},
                        "model": {"enum": [NIC_MODEL_CONNECTX_5, NIC_MODEL_CONNECTX_6]},
                    }
                },
            ],
            "required": ["kind", "model"],
        },
        "flavour_desc": {
            "title": "FABRIC Flavour",
            "type": "object",
            "properties": {
                "core": {
                    "type": "integer",
                    "description": "Number of cores in the node. Default: 2 cores",
                },
                "mem": {
                    "type": "integer",
                    "description": "Amount of ram in the node. Default: 8 GB",
                },
                "disk": {
                    "type": "integer",
                    "description": "Amount of disk space n the node. Default: 10 GB",
                },
            },
            "required": ["core", "mem"],
            "additionalProperties": False,
        },
    },
}


class EnosFabricFormatError(EnosError): ...  # noqa: E701


FabricFormatChecker = FormatChecker()


@FabricFormatChecker.checks("walltime", raises=EnosFabricFormatError)
def is_valid_walltime(instance) -> bool:
    """Auxiliary function to check walltime format"""
    if not isinstance(instance, str):
        return False
    try:
        # HH:MM
        wt_str = instance.split(":")
        int(wt_str[0])
        int(wt_str[1])
        return True
    except Exception as err:
        raise EnosFabricFormatError(
            "Walltime must be specified in HH:MM:SS format"
        ) from err


@FabricFormatChecker.checks("ip", raises=EnosFabricFormatError)
def is_valid_ip_cidr(instance) -> bool:
    if not isinstance(instance, str):
        return False
    try:
        ip_network(instance)
        return True
    except Exception as err:
        raise EnosFabricFormatError("Value must be a valid IPv4 or IPv6 CIDR") from err


@FabricFormatChecker.checks("ipv4", raises=EnosFabricFormatError)
def is_valid_ipv4_cidr(instance) -> bool:
    if not isinstance(instance, str):
        return False
    try:
        IPv4Network(instance)
        return True
    except Exception as err:
        raise EnosFabricFormatError("Value must be a valid IPv4 CIDR") from err


@FabricFormatChecker.checks("ipv6", raises=EnosFabricFormatError)
def is_valid_ipv6_cidr(instance) -> bool:
    if not isinstance(instance, str):
        return False
    try:
        IPv6Network(instance)
        return True
    except Exception as err:
        raise EnosFabricFormatError("Value must be a valid IPv6 CIDR") from err


def FabricValidator(schema) -> Draft7Validator:
    return Draft7Validator(schema, format_checker=FabricFormatChecker)
