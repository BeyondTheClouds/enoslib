import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "tiny",
            "number": 1,
        }, {
            "roles": ["compute"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"cidr": "192.168.40.0/24", "roles": ["mynetwork"]}]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["control", "compute"]
}


# claim the resources
conf = VagrantConf.from_dictionnary(provider_conf)

provider = Vagrant(conf)
roles, networks = provider.init()

roles = sync_info(roles, networks)

netem = NetemHTB(tc, roles=roles)
# apply network constraints
netem.deploy()

# validate network constraints
netem.validate()

# reset network constraints
netem.destroy()

# validate network constraints and saving in an alternative
netem.validate(output_dir="after_reset")
