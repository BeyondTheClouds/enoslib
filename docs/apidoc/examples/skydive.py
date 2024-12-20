import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()


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

s = en.Skydive(analyzers=roles["control"], agents=roles["compute"] + roles["control"])
s.deploy()

ui_address = roles["control"][0].address
print("The UI is available at http://%s:8082" % ui_address)

s.backup()
s.destroy()

# destroy the boxes
provider.destroy()
