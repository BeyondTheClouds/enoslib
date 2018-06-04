from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_g5k.provider import G5k

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "resources": {
        "machines": [{
            "role": "control",
            "cluster": "paravance",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        }],
        "networks": [
          {
            "id": "n1",
            "type": "prod",
            "role": "my_network",
            "site": "rennes"
          },
          {
            "id": "not_linked_to_any_machine",
            "type": "slash_22",
            "role": "my_subnet",
            "site": "rennes",
         }]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
provider = G5k(provider_conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the reservation
provider.destroy()
