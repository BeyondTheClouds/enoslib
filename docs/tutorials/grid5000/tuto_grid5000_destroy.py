import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        walltime="0:20:00",
    )
    .add_machine(roles=["nancy"], cluster="gros", nodes=1)
    .add_machine(roles=["rennes"], cluster="paravance", nodes=1)
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

en.run_command("uname -a", roles=roles)

# Destroy jobs
provider.destroy()

# This should create new jobs, not reload the previous jobs
provider = en.G5k(conf)
roles, networks = provider.init()

en.run_command("uname -a", roles=roles)

# Release all Grid'5000 resources
provider.destroy()
