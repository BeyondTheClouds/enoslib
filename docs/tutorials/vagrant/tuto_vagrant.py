from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "tiny",
            "number": 1,
        },{
            "roles": ["control", "compute"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}]
    }
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_dictionnary(provider_conf)
provider = Enos_vagrant(conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the boxes
# provider.destroy()
