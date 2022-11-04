import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(
        job_type=["deploy"],
        env_name="ubuntu2004-min",
        job_name=job_name,
        walltime="00:50:00",
    )
    .add_machine(roles=["rennes"], cluster="paravance", nodes=1)
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Install packages
with en.actions(roles=roles) as a:
    a.apt(name=["htop", "iotop"], state="present", update_cache="yes")


# Release all Grid'5000 resources
provider.destroy()
