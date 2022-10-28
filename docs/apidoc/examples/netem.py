import logging

import enoslib as en

en.init_logging(level=logging.INFO)

conf = (
    en.VagrantConf()
    .add_machine(roles=["control"], flavour="tiny", number=1)
    .add_machine(roles=["compute"], flavour="tiny", number=1)
    .add_network(roles=["mynetwork"], cidr="192.168.42.0/24")
    .finalize()
)

# claim the resources
provider = en.Vagrant(conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
roles = en.sync_info(roles, networks)

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["control", "compute"],
}

netem = en.Netem(tc, roles=roles)
netem.deploy()
netem.validate()
netem.backup()
netem.destroy()

# destroy the boxes
provider.destroy()
