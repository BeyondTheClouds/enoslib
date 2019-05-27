from enoslib.api import discover_networks, emulate_network, validate_network
from enoslib.infra.enos_chameleonbaremetal.provider import Chameleonbaremetal
from enoslib.infra.enos_chameleonbaremetal.configuration import Configuration

import logging

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
conf = Configuration.from_dictionnary(provider_conf)
provider = Chameleonbaremetal(conf)
# provider.destroy()
roles, networks = provider.init()
discover_networks(roles, networks)

emulate_network(tc, roles=roles)
validate_network(roles=roles)

provider.destroy()
