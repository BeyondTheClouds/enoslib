# -*- coding: utf-8 -*-

from enoslib.host import Host
from enoslib.infra.provider import Provider
from enoslib.utils import get_roles_as_list

SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"},
        # Mandatory keys
        "key_name": {"type": "string"},
        "image": {"type": "string"},
        "user": {"type": "string"}
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
            "anyOf": [
                {"roles": {"type": "array", "items": {"type": "string"}}},
                {"role": {"type": "string"}}
            ],
            "address": {"type": "string"},
            "alias": {"type": "string"},
            "user": {"type":  "string"},
            "keyfile": {"type": "string"},
            "port": {"type": "number"},
            "extra": {"type": "object"}
            # This may contain the network mapping
            # network role -> interfaces
            # if auto-discovery network feature isn't used
        },
        "required": [
            "address"
        ]
    },

    "network": {
        "type": "object",
        "properties": {
            "anyOf": [
                {"roles": {"type": "array", "items": {"type": "string"}}},
                {"role": {"type": "string"}}
            ],
            # TODO(msimonin): validate the ip schema
            "start": {"type": "string"},
            "end": {"type": "string"},
            "cidr": {"type": "string"},
            "gateway": {"type": "string"},
            "dns": {"type": "string"}
        },
        "required": ["cidr"]
    }
}


class Static(Provider):

    def init(self, force_deploy=False):
        resources = self.provider_conf["resources"]
        machines = resources["machines"]
        roles = {}
        for machine in machines:
            rs = get_roles_as_list(machine)
            for r in rs:
                roles.setdefault(r, []).append(
                    Host(machine["address"],
                         alias=machine.get("alias"),
                         user=machine.get("user"),
                         keyfile=machine.get("keyfile"),
                         port=machine.get("port"),
                         extra=machine.get("extra")))
        return roles, resources["networks"]

    def destroy(self):
        pass

    def default_config(self):
        return {}

    def schema(self):
        return SCHEMA
