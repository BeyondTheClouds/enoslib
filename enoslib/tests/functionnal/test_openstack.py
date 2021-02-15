from enoslib.api import sync_info
from enoslib.infra.enos_openstack.provider import Openstack
from enoslib.infra.enos_openstack.configuration import Configuration
from enoslib.service import Netem

import logging
import os

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "key_name": "enos_matt",
    "user": "cc",
    "image": "CC-Ubuntu16.04",
    "prefix": "plop",
    "resources": {
        "machines": [
            {"roles": ["control"], "flavour": "m1.medium", "number": 1},
            {"roles": ["compute"], "flavour": "m1.medium", "number": 5},
        ],
        "networks": ["network_interface"],
    },
}

tc = {"enable": True, "default_delay": "20ms", "default_rate": "1gbit"}
inventory = os.path.join(os.getcwd(), "hosts")
conf = Configuration.from_dictionnary(provider_conf)
provider = Openstack(conf)
roles, networks = provider.init()
roles = sync_info(roles, networks)
netem = Netem(tc, roles=roles)
netem.deploy()
netem.validate()
