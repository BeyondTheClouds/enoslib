import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# fmt: off
conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name, walltime="0:10:00")
    # For convenience, we use the site name as role
    .add_machine(roles=["rennes", "intel"], cluster="paravance", nodes=1)
    .add_machine(roles=["lille", "amd"], cluster="chiclet", nodes=1)
)
# fmt: on

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Check connectivity from Rennes to Lille
target = roles["lille"][0]
results = en.run_command(f"ping -c3 {target.address}", roles=roles["rennes"])
for result in results:
    print(f"Ping from {result.host} to {target.address}:")
    print(f"{result.stdout}")


# Release all Grid'5000 resources
provider.destroy()
