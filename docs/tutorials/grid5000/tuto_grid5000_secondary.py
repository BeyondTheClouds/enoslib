import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)


SITE = "rennes"
CLUSTER = "paravance"

network = G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
private = G5kNetworkConf(id="n2", type="kavlan", roles=["private"], site=SITE)

conf = (
    G5kConf()
    .add_network_conf(network)
    .add_network_conf(private)
    .add_machine(
        roles=["server"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=network,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["client"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=network,
        secondary_networks=[private],
    )
    .finalize()
)

provider = G5k(conf)
roles, networks = provider.init()
provider.destroy()
