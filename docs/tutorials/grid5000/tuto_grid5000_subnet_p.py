import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name


prod_network = en.G5kNetworkConf(type="prod", roles=["my_network"], site="rennes")
conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_16",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=prod_network
    )
    .finalize()
)

provider = en.G5k(conf)

# Get actual resources
try:
    roles, networks = provider.init()
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
