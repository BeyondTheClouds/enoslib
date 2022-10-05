import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

SITE = "rennes"
CLUSTER = "paravance"

network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
private = en.G5kNetworkConf(id="n2", type="kavlan", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(job_name=job_name)
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
