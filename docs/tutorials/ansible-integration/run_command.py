import json
import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "backend": "libvirt",
    "box": "generic/debian9",
    "resources": {
        "machines": [{
            "roles":  ["control1"],
            "flavour": "tiny",
            "number": 1,
        },{
            "roles": ["control2"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}]
    }
}

conf = VagrantConf.from_dictionnary(provider_conf)
provider = Vagrant(conf)
roles, networks = provider.init()
roles = discover_networks(roles, networks)
result = run_command("date",
                     pattern_hosts="control*",
                     roles=roles)
with open("result_ok", "w") as f:
    json.dump(result["ok"], f, indent=2)
with open("result_failed", "w") as f:
    json.dump(result["failed"], f, indent=2)
