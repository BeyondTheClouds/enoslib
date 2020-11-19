import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)


# claim the resources
network = G5kNetworkConf(
    id="n1", type="kavlan", roles=["my_network"], site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=__file__)
    .add_network_conf(network)
    .add_machine(
        roles=["control"], cluster="parapluie", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["control", "compute"],
        cluster="parapluie",
        nodes=1,
        primary_network=network,
    )
    .finalize()
)

provider = G5k(conf)
roles, networks = provider.init()

# destroy the reservation
provider.destroy()
