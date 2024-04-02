import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

CLUSTER = "chifflot"

conf = en.G5kConf.from_settings(
    job_type=[], job_name=job_name, walltime="0:30:00"
).add_machine(roles=["gpu"], cluster=CLUSTER, nodes=1)

provider = en.G5k(conf)
roles, networks = provider.init()


registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)

# First Docker installation with no nvidia toolkit
d = en.Docker(
    agent=roles["gpu"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
    nvidia_toolkit=False,
)
d.deploy()

# Check that nvidia support is not installed
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    roles=roles["gpu"],
    ignore_errors=True,
)
assert results[0].rc != 0

# Then let Enoslib auto-detect the GPU
d = en.Docker(
    agent=roles["gpu"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
)
d.deploy()

# Check that nvidia support is correctly installed
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi", roles=roles["gpu"]
)
assert results[0].rc == 0


# Release all Grid'5000 resources
provider.destroy()
