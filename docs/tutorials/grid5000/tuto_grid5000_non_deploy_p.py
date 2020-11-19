import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)


# claim the resources
network = G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)

conf = (
    G5kConf.from_settings(
        job_type="allow_classic_ssh", job_name="test-non-deploy"
    )
    .add_network_conf(network)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["control", "network"],
        cluster="paravance",
        nodes=1,
        primary_network=network,
    )
    .finalize()
)


provider = G5k(conf)
roles, networks = provider.init()
print(roles)
print(networks)
