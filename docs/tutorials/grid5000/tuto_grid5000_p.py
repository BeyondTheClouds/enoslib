import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
network = G5kNetworkConf(
    id="n1", type="kavlan", roles=["my_network"], site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=job_name)
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
# Get actual resources
roles, networks = provider.init()