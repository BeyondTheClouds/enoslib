from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_chameleonbaremetal.provider import Chameleonbaremetal
from enoslib.infra.enos_chameleonbaremetal.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "key_name": "enos_matt",
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "compute_skylake",
            "number": 1,
        },{
            "roles": ["compute"],
            "flavour": "compute_skylake",
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
conf = Configuration.from_dictionnary(provider_conf)
provider = Chameleonbaremetal(conf)
# provider.destroy()
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
provider.destroy()
