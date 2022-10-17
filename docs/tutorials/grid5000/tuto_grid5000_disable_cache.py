import logging
from pathlib import Path

import enoslib as en
from enoslib.config import set_config


en.init_logging(level=logging.INFO)


# Disabling the cache
set_config(g5k_cache=False)

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name, walltime="0:10:00")
    .add_machine(roles=["control"], cluster="paravance", nodes=1)
    .add_machine(
        roles=["control", "network"],
        cluster="paravance",
        nodes=1,
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
