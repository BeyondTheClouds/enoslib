from enoslib.api import generate_inventory, run_ansible
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import os
import logging


logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control1"],
            "flavor": "tiny",
            "number": 1,
        },{
            "roles": ["control2"],
            "flavor": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}]
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
conf = Configuration.from_dictionnary(provider_conf)
provider = Enos_vagrant(conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
run_ansible(["site.yml"], inventory)
