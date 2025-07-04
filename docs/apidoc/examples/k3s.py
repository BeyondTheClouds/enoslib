import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# claim the resources
conf = (
    en.G5kConf.from_settings(job_name=job_name, walltime="0:45:00", job_type=[])
    .add_machine(roles=["master"], cluster="paradoxe", nodes=1)
    .add_machine(roles=["agent"], cluster="paradoxe", nodes=10)
    .finalize()
)


provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()

# Available Versions here : https://github.com/k3s-io/k3s/releases
k3s = en.K3s(
    master=roles["master"],
    agent=roles["agent"],
    data_dir="/tmp/k3s_state",
    version="v1.32.5+k3s1",
    dashboard=True,
)

k3s.deploy()
