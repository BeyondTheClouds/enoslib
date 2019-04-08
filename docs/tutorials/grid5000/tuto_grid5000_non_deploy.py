from enoslib.api import generate_inventory
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "job_type": "allow_classic_ssh",
#    "job_name": "test-non-deploy",
    "oargrid_jobids": [["rennes", 1139779]],
    "resources": {
        "machines": [{
            "roles": ["control"],
            "cluster": "parapluie",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        },{

            "roles": ["control", "compute"],
            "cluster": "parapluie",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        }],
        "networks": [{
            "id": "n1",
            "type": "prod",
            "roles": ["my_network"],
            "site": "rennes",
         }]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_dictionnary(provider_conf)
provider = G5k(conf)

roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the reservation
provider.destroy()
