from enoslib.api import emulate_network,\
    validate_network, reset_network, check_networks, generate_inventory
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "libvirt",
    "box": "generic/debian9",
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        },{
            "roles": ["compute"],
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


# claim the resources
conf = Configuration.from_dictionnary(provider_conf)

provider = Enos_vagrant(conf)
roles, networks = provider.init()

generate_inventory(roles, networks, "hosts.ini")
check_networks(roles, networks)
generate_inventory(roles, networks, "hosts.ini")

# apply network constraints
emulate_network(roles, tc)

# validate network constraints
validate_network(roles)

# reset network constraints
reset_network(roles)

# validate network constraints and saving in an alternative
validate_network(roles, output_dir="after_reset")
