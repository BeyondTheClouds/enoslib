from enoslib.api import sync_info
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration as VagrantConf
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration as StaticConf
from enoslib.service import Netem

import logging
import os


logging.basicConfig(level=logging.DEBUG)


provider_conf = {
    "resources": {
        "machines": [
            {"roles": ["control"], "flavour": "tiny", "number": 1},
            {"roles": ["compute"], "flavour": "tiny", "number": 1},
        ],
        "networks": [{"cidr": "192.168.20.0/24", "roles": ["mynetwork"]}],
    }
}

tc = {"enable": True, "default_delay": "20ms", "default_rate": "1gbit"}
inventory = os.path.join(os.getcwd(), "hosts")
print("Starting ressources with the provider vagrant")
provider = Enos_vagrant(VagrantConf.from_dictionnary(provider_conf))
roles, networks = provider.init()
print("Building the machine list")
resources = {"machines": [], "networks": []}

for role, machines in roles.items():
    for machine in machines:
        resources["machines"].append(
            {
                "address": machine.address,
                "alias": machine.alias,
                "user": machine.user,
                "port": int(machine.port),
                "keyfile": machine.keyfile,
                "roles": [role],
            }
        )

resources["networks"] = networks


provider = Static(StaticConf.from_dictionnary({"resources": resources}))
roles, networks = provider.init()
roles = sync_info(roles, networks)
netem = Netem(tc, roles=roles)
netem.deploy()
netem.validate()
