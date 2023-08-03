import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# Set very high parallelism to be able to handle a large number of VMs
en.set_config(ansible_forks=100)

job_name = Path(__file__).name

conf = en.VMonG5kConf.from_settings(job_name=job_name, walltime="0:45:00").add_machine(
    roles=["fog"],
    cluster="dahu",
    number=200,
    flavour_desc={"core": 1, "mem": 2048},
)

provider = en.VMonG5k(conf)

# Get actual resources
roles, networks = provider.init()

# Wait for VMs to finish booting
en.wait_for(roles)

# Run same command on all VMs
results = en.run_command("uname -a", roles=roles)
for result in results:
    print(result.payload["stdout"])


# Release all Grid'5000 resources
provider.destroy()
