from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import os

provider_conf = {
    "resources": {
        "machines": [{
            "role": "control",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        },{
            "role": "compute",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        }]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
provider = Enos_vagrant(provider_conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)

# apply network constraints
emulate_network(roles, inventory, tc)

# validate network constraints
validate_network(roles, inventory)
