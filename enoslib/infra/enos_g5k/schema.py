# -*- coding: utf-8 -*-

from jsonschema import validate

KAVLAN = "kavlan"
KAVLAN_LOCAL = "kavlan-local"
KAVLAN_GLOBAL = "kavlan-global"
KAVLAN_TYPE = [KAVLAN, KAVLAN_LOCAL, KAVLAN_GLOBAL]

SLASH_22 = "slash_22"
SLASH_18 = "slash_18"
SUBNET_TYPE = [SLASH_18, SLASH_22]

PROD = "prod"

NETWORK_TYPES = [PROD] + KAVLAN_TYPE + SUBNET_TYPE

# This is the schema for the abstract description of the resources
SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"}
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
        "required": ["machines", "networks"],
    },

    "machine": {
        "title": "Compute",
        "type": "object",
        "properties": {
            "anyOf": [
                {"roles": {"type": "array", "items": {"type": "string"}}},
                {"role": {"type": "string"}}
            ],
            "cluster": {"type": "string"},
            "nodes": {"type": "number"},
            "min": {"type": "number"},
            "primary_network": {"type": "string"},
            "secondary_networks": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True}
        },
        "required": [
            "nodes",
            "cluster",
            "primary_network"
        ]
    },
    "network": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"enum": NETWORK_TYPES},
            "anyOf": [
                {"roles": {"type": "array", "items": {"type": "string"}}},
                {"role": {"type": "string"}}
            ],
            "site": {"type": "string"}
        },
        "required": ["id", "type", "site"]
    }
}


def validate_schema(provider_conf):
    """Validate the schema of the configuration.

    Args:
        provider_conf (dict): The provider configuration
    """
    # First, validate the syntax
    validate(provider_conf, SCHEMA)
    # Second, validate the network names
    # _validate_network_names(d)
    # Third validate the network number on each nodes


def _validate_network_names(resources):
    # every network role used in the machine descriptions should fit with one
    # in network
    pass


def _validate_network_number(resources):
    # The number of network wanted for each node should fit the number of NIC
    # available on g5k
    pass
