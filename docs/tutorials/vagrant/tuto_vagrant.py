from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "virtualbox",
    "user": "root",
    "resources": {
        "machines": [{
            "role": "control",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        },{
            "roles": ["control", "compute"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        }]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
provider = Enos_vagrant(provider_conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the boxes
provider.destroy()
