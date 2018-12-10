from enoslib.api import generate_inventory, run_command
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration

import json
import os

# Dummy functionnal test running inside a docker container

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "address": "localhost",
            "extra": {
                "ansible_connection": "local"
            }
        }],
        "networks": [{
            "roles": ["local"],
            "start": "172.17.0.0",
            "end": "172.17.255.255",
            "cidr": "172.17.0.0/16",
            "gateway": "172.17.0.1",
            "dns": "172.17.0.1",
        }]
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
provider = Static(Configuration.from_dictionnary(provider_conf))
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
result = run_command("control", "date", inventory)
print(json.dumps(result))
