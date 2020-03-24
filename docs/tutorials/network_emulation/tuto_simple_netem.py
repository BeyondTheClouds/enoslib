from enoslib.api import discover_networks
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration
from enoslib.service import SimpleNetem

import logging
import os

logging.basicConfig(level=logging.DEBUG)


prod_network = NetworkConfiguration(
    id="n1",
    type="prod",
    roles=["my_network"],
    site="rennes"
)
conf = (
    Configuration.from_settings(job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_machine(
        roles=["city", "paris"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
)
provider = G5k(conf)
roles, networks = provider.init()
roles = discover_networks(roles, networks)

netem = SimpleNetem("delay 10ms", "my_network", hosts=roles["city"])
netem.deploy()
netem.validate()
netem.destroy()
