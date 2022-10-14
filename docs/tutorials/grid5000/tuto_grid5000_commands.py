import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name)
    .add_machine(roles=["compute", "control"], cluster="paravance", nodes=1)
    .add_machine(
        roles=["compute"],
        cluster="paravance",
        nodes=1,
    )
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()

    # Run a command on all hosts belonging to a given role
    results = en.run_command("nproc", roles=roles["compute"])
    for result in results:
        print(f"{result.host} has {result.payload['stdout']} logical CPU cores")

    # Run a command on all hosts, whatever their roles
    results = en.run_command("uname -a", roles=roles)
    for result in results:
        print(result.payload["stdout"])
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
