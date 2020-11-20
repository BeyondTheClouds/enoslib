import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
network = G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)

conf = (
    G5kConf.from_settings(
        job_type="allow_classic_ssh", job_name=job_name
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
try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuffs here
    # ...
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
