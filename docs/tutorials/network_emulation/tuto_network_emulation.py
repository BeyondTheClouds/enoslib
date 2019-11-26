from enoslib.api import discover_networks
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration
from enoslib.service import Netem

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
    Configuration()
    .add_network_conf(prod_network)
    .add_machine(
        roles=["paris"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["berlin"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["londres"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
)
provider = G5k(conf)
roles, networks = provider.init()
roles = discover_networks(roles, networks)

# Building the network constraints
emulation_conf = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "constraints": [{
        "src": "paris",
        "dst": "londres",
        "symetric": True,
        "delay": "10ms"
    }]
}

logging.info(emulation_conf)

netem = Netem(emulation_conf, roles=roles)
netem.deploy()
netem.validate()
