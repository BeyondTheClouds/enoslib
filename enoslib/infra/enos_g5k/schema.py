from jsonschema import validate

KAVLAN = "kavlan"
KAVLAN_LOCAL = "kavlan-local"
KAVLAN_GLOBAL = "kavlan-global"
PROD = "prod"
NETWORK_TYPES = [PROD, KAVLAN_GLOBAL, KAVLAN_LOCAL, KAVLAN]

# This is the schema for the abstract description of the resources
SCHEMA = {
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


def validate_schema(resources):
    # First, validate the syntax
    validate(resources, SCHEMA)
    # Second, validate the network names
    _validate_network_names(resources)
    # Third validate the network number on each nodes


def _validate_network_names(resources):
    # every network role used in the machine descriptions should fit with one
    # in network
    pass


def _validate_network_number(resources):
    # The number of network wanted for each node should fit the number of NIC
    # available on g5k
    pass
