import json
import logging

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "backend": "libvirt",
    "box": "generic/debian9",
    "resources": {
        "machines": [
            {
                "roles": ["control1"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["control2"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}],
    },
}

conf = en.VagrantConf.from_dictionnary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)
result = en.run_command("date", pattern_hosts="control*", roles=roles)
print(result)

# shortcut 1 -> use the roles
result = en.run("date", roles)
print(result)

# shortcut 2 -> use a list of hosts
result = en.run("date", roles["control1"])
print(result)

# shortcut 3 -> use a single host
result = en.run("date", roles["control1"][0])
print(result)

# async tasks / will run in detached mode
result = en.run("date", roles=roles, background=True)
print(result)
