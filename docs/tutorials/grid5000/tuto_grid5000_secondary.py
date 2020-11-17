from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration

import logging


logging.basicConfig(level=logging.INFO)


SITE = "rennes"
CLUSTER = "paravance"

network = NetworkConfiguration(id="n1", type="prod", roles=["my_network"], site=SITE)
private = NetworkConfiguration(id="n2", type="kavlan", roles=["private"], site=SITE)

conf = (
    Configuration()
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
