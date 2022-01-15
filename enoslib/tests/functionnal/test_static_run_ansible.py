from enoslib.api import generate_inventory, run_ansible, CommandResult
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration

import logging
import os

# Dummy functionnal test running inside a docker container
logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "alias": "test_machine",
                "address": "localhost",
                "extra": {"ansible_connection": "local"},
            },
        ],
        "networks": [
            {
                "roles": ["local"],
                "start": "172.17.0.0",
                "end": "172.17.255.255",
                "cidr": "172.17.0.0/16",
                "gateway": "172.17.0.1",
                "dns": "172.17.0.1",
            }
        ],
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
provider = Static(Configuration.from_dictionnary(provider_conf))
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=False)
results = run_ansible(["site.yml"], inventory_path=inventory, on_error_continue=True)
result = results.filter(host="test_machine", status="OK", task="One task")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


results = run_ansible(["site.yml"], roles=roles)
result = results.filter(host="test_machine", status="OK", task="One task")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""