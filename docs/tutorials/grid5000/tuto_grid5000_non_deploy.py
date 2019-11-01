from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration

import logging
import os


logging.basicConfig(level=logging.INFO)


provider_conf = {
    "job_type": "allow_classic_ssh",
    "job_name": "test-non-deploy",
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
conf = Configuration.from_dictionnary(provider_conf)

provider = G5k(conf)
roles, networks = provider.init()

# destroy the reservation
provider.destroy()
