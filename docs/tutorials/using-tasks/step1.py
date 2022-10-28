import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["compute"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"cidr": "192.168.40.0/24", "roles": ["mynetwork"]}],
    },
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["control", "compute"],
}


# claim the resources
conf = en.VagrantConf.from_dictionary(provider_conf)

provider = en.Vagrant(conf)
roles, networks = provider.init()

roles = en.sync_info(roles, networks)

netem = en.NetemHTB(tc, roles=roles)
# apply network constraints
netem.deploy()

# validate network constraints
netem.validate()

# reset network constraints
netem.destroy()

# validate network constraints and saving in an alternative
netem.validate(output_dir="after_reset")
