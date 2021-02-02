import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name


prod_network = G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=job_name,
                          job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_16",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(
        roles=["control"], cluster="parapluie", nodes=1, primary_network=prod_network
    )
    .finalize()
)

provider = G5k(conf)

# Get actual resources
roles, networks = provider.init()