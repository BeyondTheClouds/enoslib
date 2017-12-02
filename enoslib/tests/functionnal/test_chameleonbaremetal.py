from enoslib.api import generate_inventory, emulate_network, validate_network, wait_ssh
from enoslib.infra.enos_chameleonbaremetal.provider import Chameleonbaremetal

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "key_name": "enos-matt",
    "resources": {
        "machines": [{
            "role": "control",
            "flavor": "storage",
            "number": 1,
        },{
            "role": "compute",
            "flavor": "compute",
            "number": 1,
        }],
        "networks": ["network_interface"]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}
inventory = os.path.join(os.getcwd(), "hosts")
provider = Chameleonbaremetal(provider_conf)
provider.destroy()
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
provider.destroy()
