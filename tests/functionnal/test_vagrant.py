from enoslib.api import generate_inventory, emulate_network, validate_network, run_command
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import os
import logging


logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "backend": "virtualbox",
    "user": "root",
    "box": "debian/jessie64",
    "resources": {
        "machines": [{
            "role": "control1",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n2"]
        },{
            "role": "control2",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n3"]
        }]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}
inventory = os.path.join(os.getcwd(), "hosts")
provider = Enos_vagrant(provider_conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
#result = run_command("control*", "ping -c 1 {{hostvars['enos-1']['ansible_' + n1].ipv4.address}}", inventory)
result = run_command("control*", "date", inventory)
print(result["ok"])
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
