# Make sure your run this example from a dedicated Grid'5000 control node.
# See https://discovery.gitlabpages.inria.fr/enoslib/tutorials/performance_tuning.html

import logging
import os
import resource
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# Set very high parallelism to be able to handle a large number of VMs
# simultaneously.  This takes around 25 GB RAM on the control node.
en.set_config(ansible_forks=1000)

# Increase ulimit -n, otherwise we run out of file descriptors
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
new_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
print(f"Increased number of file descriptors from {soft} to {new_soft}")

# Enable Ansible pipelining
os.environ["ANSIBLE_PIPELINING"] = "True"

job_name = Path(__file__).name

# By default, EnOSlib uses a /22 network, which is not large enough for
# us, so let's use a /16 instead.
conf = en.VMonG5kConf.from_settings(
    job_name=job_name, walltime="01:00:00", subnet_type="slash_16"
).add_machine(
    roles=["fog"],
    cluster="paradoxe",
    number=3000,
    vcore_type="thread",
    flavour_desc={"core": 1, "mem": 2048},
)

provider = en.VMonG5k(conf)

# Get actual resources
roles, networks = provider.init()

# Wait for VMs to finish booting and for the network to figure out all
# those new IP/MAC addresses.
en.wait_for(roles)

# Run same command on all VMs
results = en.run_command("uname -a", roles=roles)
for result in results:
    print(result.payload["stdout"])


# Release all Grid'5000 resources
provider.destroy()
