import logging
from pathlib import Path

import enoslib as en
from enoslib.config import set_config


en.init_logging(level=logging.DEBUG)


# Disabling the cache
set_config(g5k_cache=False)

job_name = Path(__file__).name

# claim the resources
network = en.G5kNetworkConf(type="prod", roles=["my_network"], site="rennes")


conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name)
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

provider = en.G5k(conf)
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
