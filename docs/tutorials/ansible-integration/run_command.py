from enoslib.api import discover_networks, run_command
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import json
import logging


logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "backend": "libvirt",
    "box": "generic/debian9",
    "resources": {
        "machines": [{
            "roles":  ["control1"],
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

conf = Configuration.from_dictionnary(provider_conf)
provider = Enos_vagrant(conf)
roles, networks = provider.init()
discover_networks(roles, networks)
result = run_command("control*", "date", roles=roles)
with open("result_ok", "w") as f:
    json.dump(result["ok"], f, indent=2)
with open("result_failed", "w") as f:
    json.dump(result["failed"], f, indent=2)
