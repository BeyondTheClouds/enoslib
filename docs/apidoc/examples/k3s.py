import logging

from enoslib import *


logging.basicConfig(level=logging.INFO)

# claim the resources
network = G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site="rennes")

conf = (
    G5kConf.from_settings(job_type="allow_classic_ssh", job_name="k3s")
    .add_network_conf(network)
    .add_machine(
        roles=["master"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["agent"], cluster="parapluie", nodes=10, primary_network=network
    )
    .finalize()
)


provider = G5k(conf)
# Get actual resources
roles, networks = provider.init()


k3s = K3s(master=roles["master"], agent=roles["agent"])
k3s.deploy()
