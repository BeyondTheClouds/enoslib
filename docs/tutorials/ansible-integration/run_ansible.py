from enoslib.api import generate_inventory, run_ansible
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import os
import logging


logging.basicConfig(level=logging.DEBUG)

provider_conf = {
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

inventory = os.path.join(os.getcwd(), "hosts")
provider = Enos_vagrant(provider_conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
run_ansible(["site.yml"], inventory)
