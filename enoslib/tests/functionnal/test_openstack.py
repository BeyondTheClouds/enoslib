from enoslib.api import generate_inventory, emulate_network, validate_network, wait_ssh
from enoslib.infra.enos_openstack.provider import Openstack
from enoslib.infra.enos_openstack.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "key_name": "enos_matt",
    "user": "cc",
    "image":"CC-Ubuntu16.04",
    "prefix": "plop",
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "m1.medium",
            "number": 1,
        },{
            "roles": ["compute"],
            "flavour": "m1.medium",
            "number": 5,
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
provider = Openstack(conf)
provider.destroy()
roles, networks = provider.init()
generate_inventory(roles, networks, inventory)
wait_ssh(inventory)
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
