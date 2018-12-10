from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "cluster": "parapluie",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        }],
        "networks": [
          {
            "id": "n1",
            "type": "prod",
            "roles": ["my_network"],
            "site": "rennes"
          },
          {
            "id": "not_linked_to_any_machine",
            "type": "slash_22",
            "roles": ["my_subnet"],
            "site": "rennes",
         }]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuratin.from_dictionnary(provider_conf)
provider = G5k(conf)
roles, networks = provider.init()

# Retrieving subnet
subnet = [n for n in networks if "my_subnet" in n["roles"]]
logging.info(subnet)
# This returns the subnet information
# {
#    'roles': ['my_subnet'],
#    'start': '10.158.0.1',
#    'dns': '131.254.203.235',
#    'end': '10.158.3.254',
#    'cidr': '10.158.0.0/22',
#    'gateway': '10.159.255.254'
#    'mac_end': '00:16:3E:9E:03:FE',
#    'mac_start': '00:16:3E:9E:00:01',
# } 

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the reservation
provider.destroy()
