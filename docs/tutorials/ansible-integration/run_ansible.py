import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
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
    }
}

conf = VagrantConf.from_dictionnary(provider_conf)
provider = Vagrant(conf)
roles, networks = provider.init()

result = run_ansible(["site.yml"], roles=roles)
print(result)
