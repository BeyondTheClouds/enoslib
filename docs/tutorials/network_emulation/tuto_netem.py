import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

prod_network = G5kNetworkConf(
    id="n1",
    type="prod",
    roles=["my_network"],
    site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=job_name, job_type="allow_classic_ssh")
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
roles = sync_network_info(roles, networks)

# Building the network constraints
emulation_conf = {
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "except": [],
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
netem.destroy()