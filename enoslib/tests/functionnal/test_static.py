from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration as VagrantConf
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration as StaticConf

import os

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n2"]
        },{
            "roles": ["compute"],
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
print("Starting ressources with the provider vagrant")
provider = Enos_vagrant(VagrantConf.from_dictionnary(provider_conf))
roles, networks = provider.init()
print("Building the machine list")
resources = {"machines": [], "networks": []}

for role, machines in roles.items():
    for machine in machines:
        resources["machines"].append({
            "address": machine.address,
            "alias": machine.alias,
            "user": machine.user,
            "port": int(machine.port),
            "keyfile": machine.keyfile,
            "roles": [role]
        })

resources["networks"] = networks


provider = Static(StaticConf.from_dictionnary({"resources": resources}))
roles, _ = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)

