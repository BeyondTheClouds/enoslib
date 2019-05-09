# -*- coding: utf-8 -*-

from .constants import JOB_TYPES, QUEUE_TYPES, NETWORK_TYPES


SCHEMA = {
    "type": "object",
    "properties": {
        "dhcp": {"type": "boolean"},
        "force_deploy": {"type": "boolean"},
        "env_name": {"type": "string"},
        "job_name": {"type": "string"},
        "job_type": {"type": "string", "enum": JOB_TYPES},
        "key": {"type": "string"},
        "oargrid_jobids": {"type": "array", "items": {"$ref": "#/jobids"}},
        "queue": {"type": "string", "enum": QUEUE_TYPES},
        "reservation": {"type": "string"},
        "walltime": {"type": "string"},
        "resources": {"$ref": "#/resources"}
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
            "networks": {
                "type": "array",
                "items": {"$ref": "#/network"},
                "uniqueItems": True
            },
        },
        "additionalProperties": False,
        "required": ["machines", "networks"],
    },

    "jobids": {
        "title": "JobIds",
        "type": "array",
    },

    "machine": {
        "title": "Compute",
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "string"}},
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
            "roles",
            "cluster",
            "primary_network"
        ]
    },

    "network": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "type": {"enum": NETWORK_TYPES},
            "roles": {"type": "array", "items": {"type": "string"}},
            "site": {"type": "string"}
        },
        "required": ["id", "type", "roles", "site"]
    }
}
"""
Additionnal notes

Supported network types are

    - kavlan
    - kavlan-local
    - kavlan-global
    - prod
    - slash_22 (subnet reservation)
    - slash_18 (subnet reservation)

Machines must use at least one network of type prod or kavlan*. Subnets are
optional and must not be linked to any interfaces as they are a way to
claim extra ips and corresponding macs. In this case the returned network
attributes `start` and `end` corresponds to the first and last mapping of
(ip, mac).

If a key ``oargrid_jobid`` is found, the resources will be reloaded from
the corresponding oargrid job. In this case what is described under the
``resources`` key mut be compatible with the job content.

If the keys ``oar_jobid`` and ``oar_site`` are found, the resources will be
reloaded from the corresponding oar job. In this case what is described
under the ``resources`` key mut be compatible with the job content.

"""
