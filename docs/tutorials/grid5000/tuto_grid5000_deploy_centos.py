import logging
from pathlib import Path

import enoslib as en

CLUSTER = "paravance"

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = en.G5kConf.from_settings(
    job_name=job_name,
    job_type=["deploy"],
    env_name="centosstream8-min",
    walltime="0:15:00",
).add_machine(roles=["node"], cluster=CLUSTER, nodes=1)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

results = en.run_command("uname -a", roles=roles)
for result in results:
    print(result.payload["stdout"])


# Release all Grid'5000 resources
provider.destroy()
