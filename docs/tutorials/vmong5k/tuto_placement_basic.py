# Make sure your run this example from a dedicated Grid'5000 control node.
# See https://discovery.gitlabpages.inria.fr/enoslib/tutorials/performance_tuning.html

import logging
import os
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# Set very high parallelism to be able to handle a large number of VMs
en.set_config(ansible_forks=100)

# Enable Ansible pipelining
os.environ["ANSIBLE_PIPELINING"] = "True"

job_name = Path(__file__).name

CLIENT_FLAVOUR = {"core": 1, "mem": 1024}
COMPUTE_FLAVOUR = {"core": 8, "mem": 16384}
DATABASE_FLAVOUR = {"core": 4, "mem": 8192}

# claim the resources
conf = (
    en.VMonG5kConf.from_settings(job_name=job_name, walltime="00:45:00")
    # Put as many client VMs as possible on the same physical nodes. They
    # should fit on 2 ecotype nodes (each node has 40 hyper-threads).
    .add_machine(
        roles=["clients"],
        cluster="ecotype",
        number=50,
        vcore_type="thread",
        flavour_desc=CLIENT_FLAVOUR,
    )
    # CPU-intensive VMs: don't allocate VMs on hyper-threads.  They should
    # fit on 4 dahu nodes (each node has 32 physical cores).
    .add_machine(
        roles=["cpu_intensive"],
        cluster="dahu",
        number=16,
        vcore_type="core",
        flavour_desc=COMPUTE_FLAVOUR,
    )
    # Database cluster: make sure each VM is on a separate physical host.
    # We ensure this by using multiple groups with the same role.  This
    # could be done in a loop if necessary.
    .add_machine(
        roles=["database"], cluster="ecotype", number=1, flavour_desc=DATABASE_FLAVOUR
    )
    .add_machine(
        roles=["database"], cluster="ecotype", number=1, flavour_desc=DATABASE_FLAVOUR
    )
    .add_machine(
        roles=["database"], cluster="ecotype", number=1, flavour_desc=DATABASE_FLAVOUR
    )
)

provider = en.VMonG5k(conf)

roles, networks = provider.init()

en.wait_for(roles)

# Display the mapping from VM to physical nodes
for role, vms in roles.items():
    print(f"\n=== {role} ===")
    for vm in vms:
        print(f"{vm.alias:20} {vm.address:15} {vm.pm.alias}")
