from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_static.provider import Static

import os

provider_conf = {
    "resources": {
        "machines": [{
            "role": "r1",
            "address": "localhost",
            "extra": {
                "ansible_connection": "local"
            }
        }],
        "networks": [{
            "role": "local",
            "start": "172.17.0.0",
            "end": "172.17.255.255",
            "cidr": "172.17.0.0/16",
            "gateway": "172.17.0.1",
            "dns": "172.17.0.1",
        }]
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
provider = Static(provider_conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
