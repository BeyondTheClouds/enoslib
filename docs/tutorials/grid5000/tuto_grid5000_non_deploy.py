import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)


provider_conf = {
    "job_type": "allow_classic_ssh",
    "job_name": __file__,
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "parapluie",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
            {
                "roles": ["control", "compute"],
                "cluster": "parapluie",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
        ],
        "networks": [
            {"id": "n1", "type": "prod", "roles": ["my_network"], "site": "rennes"}
        ],
    },
}

# claim the resources
conf = G5kConf.from_dictionnary(provider_conf)

provider = G5k(conf)
roles, networks = provider.init()

