from enoslib.api import discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging

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

# claim the resources
conf = Configuration.from_dictionnary(provider_conf)
provider = Enos_vagrant(conf)
roles, networks = provider.init()

# decorate hosts with network information
discover_networks(roles, networks)

print(roles)

# destroy the boxes
provider.destroy()
