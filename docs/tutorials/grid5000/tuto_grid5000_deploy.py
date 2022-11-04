import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        job_type=["deploy"],
        env_name="ubuntu2204-min",
        walltime="0:20:00",
    )
    .add_machine(roles=["groupA"], cluster="paravance", nodes=1)
    .add_machine(roles=["groupB"], cluster="parasilo", nodes=1)
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

results = en.run_command("lsb_release -a", roles=roles)
for result in results:
    print(result.payload["stdout"])


# Release all Grid'5000 resources
provider.destroy()
