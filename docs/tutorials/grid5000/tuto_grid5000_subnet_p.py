import logging
from pathlib import Path

import enoslib as en

_ = en.init_logging(logging.INFO)

job_name = Path(__file__).name


conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_16",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(roles=["control"], cluster="paravance", nodes=1)
)

provider = en.G5k(conf)

# Get actual resources
try:
    roles, networks = provider.init()

finally:
    # Clean everything
    provider.destroy()
