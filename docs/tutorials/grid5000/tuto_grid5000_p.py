from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration

import logging
import os

logging.basicConfig(level=logging.DEBUG)


# claim the resources
network = NetworkConfiguration(
    id="n1", type="kavlan", roles=["my_network"], site="rennes"
)
conf = (
    Configuration.from_settings(job_name="test-enoslib_")
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
