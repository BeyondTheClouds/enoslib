import enoslib as en

en.init_logging()

conf = (
    en.VagrantConf()
    .add_machine(roles=["control"], flavour="tiny", number=1)
    .add_machine(roles=["control", "compute"], flavour="tiny", number=1)
    .add_network(roles=["mynetwork"], cidr="192.168.42.0/24")
)

# claim the resources
provider = en.Vagrant(conf)
roles, networks = provider.init()
print(roles)
print(networks)

# destroy the boxes
provider.destroy()
