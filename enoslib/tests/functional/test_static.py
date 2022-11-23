from enoslib import Netem
from enoslib.api import sync_info
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration as VagrantConf
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration as StaticConf
from typing import Dict
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

# tc = {"enable": True, "default_delay": "20ms", "default_rate": "1gbit"}
inventory = os.path.join(os.getcwd(), "hosts")
print("Starting resources with the provider vagrant")
provider = Enos_vagrant(VagrantConf.from_dictionary(provider_conf))
roles, networks = provider.init()
print("Building the machine list")
resources: Dict = {"machines": [], "networks": []}

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


provider_snd = Static(StaticConf.from_dictionary({"resources": resources}))
roles, networks = provider_snd.init()
roles = sync_info(roles, networks)
netem = Netem()  # TODO check constraints
netem.add_constraints("delay 20ms", roles)
netem.add_constraints("bandwidth 1gbit", roles)
netem.deploy()
netem.validate()
