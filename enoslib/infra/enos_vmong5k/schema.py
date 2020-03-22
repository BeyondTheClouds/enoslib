from .constants import FLAVOURS


from enoslib.infra.enos_g5k.constants import QUEUE_TYPES, SUBNET_TYPES


STRATEGY = ["copy", "cow"]

SCHEMA = {
    "description": "VMonG5k schema.",
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"},
        "enable_taktuk": {
            "type": "boolean",
            "description": "Copy the base image on remote hosts using taktuk",
        },
        "force_deploy": {
            "type": "boolean",
            "description": "Remove and restart all virtual machines",
        },
        "gateway": {
            "type": "boolean",
            "description": "Enable access to virtual machines from outside Grid'5000",
        },
        "job_name": {"type": "string", "description": "Sets the job name"},
        "queue": {
            "type": "string",
            "enum": QUEUE_TYPES,
            "description": "Grid'5000 queue to use",
        },
        "walltime": {"type": "string", "description": "Job duration"},
        "image": {
            "type": "string",
            "description": "Path to the base image on the reserved nodes",
        },
        "skip": {"type": "number", "description": "Skip this number of IPs"},
        "strategy": {
            "type": "string",
            "enum": STRATEGY,
            "description": "Base image strategy (cow, copy)",
        },
        "subnet_type": {
            "type": "string",
            "enum": SUBNET_TYPES,
            "description": "Subnet type to use (/16, /22)",
        },
        "working_dir": {
            "type": "string",
            "description": "Remote directory that hold the image",
        },
    },
    "additionalProperties": False,
    "required": ["resources"],
    "resources": {
        "title": "Resource",
        "type": "object",
        "properties": {
            "machines": {"type": "array", "items": {"$ref": "#/machine"}},
            "networks": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
        "required": ["machines", "networks"],
    },
    "machine": {
        "description": "Machine description",
        "title": "Compute",
        "type": "object",
        "properties": {
            "roles": {
                "type": "array",
                "items": {"type": "string"},
                "description": "EnOSlib's roles",
            },
            "number": {"type": "number", "description": "Number of machines to start"},
            "flavour": {
                "type": "string",
                "enum": list(FLAVOURS.keys()),
                "description": "Predefined flavour name",
            },
            "flavour_desc": {
                "$ref": "#/flavour_desc",
                "description": "Custom flavour description",
            },
            "cluster": {
                "type": "string",
                "description": "Grid'5000 cluster for the undercloud",
            },
            "undercloud": {
                "type": "array",
                "items": {"type": "object"},
                "description": "(optional)List of Host where the VM should be started.",
            },
            "extra_devices": {
                "type": "string",
                "description": "Libvirt XML description for extra devices (e.g disks).",
            },
        },
        "required": ["roles"],
        "additionalProperties": False,
    },
    "flavour_desc": {
        "description": "Custom flavour for a virtual machine.",
        "title": "Flavour",
        "type": "object",
        "properties": {
            "core": {"type": "number", "description": "number of cores"},
            "mem": {"type": "number", "description": "memory size in MB"},
            "disk": {"type": "number", "description": "disk size in GB"},
        },
        "required": ["core", "mem"],
        "additionalProperties": False,
    },
}
