import enoslib as en

en.init_logging()

# claim the resources
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site="rennes")

conf = (
    en.G5kConf.from_settings(job_type=[], job_name="k3s")
    .add_network_conf(network)
    .add_machine(
        roles=["master"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["agent"], cluster="parapluie", nodes=10, primary_network=network
    )
    .finalize()
)


provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()


k3s = en.K3s(master=roles["master"], agent=roles["agent"])
k3s.deploy()
