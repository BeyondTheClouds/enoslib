import logging

from enoslib.api import discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration
from enoslib.service import Netem


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
}


# claim the resources
conf = Configuration.from_dictionnary(provider_conf)

provider = Enos_vagrant(conf)
roles, networks = provider.init()

roles = discover_networks(roles, networks)

netem = Netem(tc, roles=roles)
# apply network constraints
netem.deploy()

# validate network constraints
netem.validate()

# reset network constraints
netem.destroy()

# validate network constraints and saving in an alternative
netem.validate(output_dir="after_reset")
