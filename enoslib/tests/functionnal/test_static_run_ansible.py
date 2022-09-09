import enoslib as en
from enoslib.api import CommandResult

import os


logging = en.init_logging()

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
provider = en.Static(en.StaticConf.from_dictionnary(provider_conf))
roles, networks = provider.init()
en.generate_inventory(roles, networks, inventory, check_networks=False)
results = en.run_ansible(["site.yml"], inventory_path=inventory, on_error_continue=True)
result = results.filter(host="test_machine", status="OK", task="One task")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""


results = en.run_ansible(["site.yml"], roles=roles)
result = results.filter(host="test_machine", status="OK", task="One task")
assert len(result) == 1
assert isinstance(result[0], CommandResult)
assert result[0].rc == 0
assert result[0].stdout == "tototiti"
assert result[0].stderr == ""
