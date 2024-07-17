import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

WALLTIME = "0:30:00"
NORMAL_CLUSTER = "paravance"
# Specify the queue as second item: "default", "production" or "testing"
GPU_CLUSTER = ("chifflot", "default")


if GPU_CLUSTER[1] == "default":
    conf = (
        en.G5kConf.from_settings(job_type=[], job_name=job_name, walltime="0:30:00")
        .add_machine(roles=["docker", "nogpu"], cluster=NORMAL_CLUSTER, nodes=1)
        .add_machine(roles=["docker", "gpu"], cluster=GPU_CLUSTER[0], nodes=1)
    )
    provider = en.G5k(conf)
else:
    # We need two jobs because a job can only target a single queue.
    normal_conf = en.G5kConf.from_settings(
        job_type=[], job_name=job_name, walltime=WALLTIME
    ).add_machine(roles=["docker", "nogpu"], cluster=NORMAL_CLUSTER, nodes=1)
    gpu_conf = en.G5kConf.from_settings(
        queue=GPU_CLUSTER[1], job_type=[], job_name=job_name + "_gpu", walltime=WALLTIME
    ).add_machine(roles=["docker", "gpu"], cluster=GPU_CLUSTER[0], nodes=1)

    normal_provider = en.G5k(normal_conf)
    gpu_provider = en.G5k(gpu_conf)
    provider = en.Providers([normal_provider, gpu_provider])

# We need to make sure that we don't reuse a previous job (the test is not indempotent)
provider.destroy()
roles, networks = provider.init()


registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)

# 1. Docker installation with no nvidia toolkit
d = en.Docker(
    agent=roles["docker"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
    nvidia_toolkit=False,
)
d.deploy()

# Check that nvidia support is not installed
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    task_name="Nvidia support should not be installed on GPU node",
    roles=roles["gpu"],
    ignore_errors=True,
)
assert results[0].rc != 0
assert "could not select device driver" in results[0].stderr, results[0].stderr

results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    task_name="Nvidia support should not be installed on normal node",
    roles=roles["nogpu"],
    ignore_errors=True,
)
assert results[0].rc != 0
assert "could not select device driver" in results[0].stderr, results[0].stderr


# 2. Let Enoslib auto-detect the GPU
d = en.Docker(
    agent=roles["docker"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
)
d.deploy()

# Check that nvidia support is correctly installed on GPU node
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    task_name="Nvidia support should be installed on GPU node (auto-detected)",
    roles=roles["gpu"],
)
assert results[0].rc == 0

# Check that nvidia support is not installed on regular node
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    task_name="Nvidia support should not be installed on normal node (auto-detected)",
    roles=roles["nogpu"],
    ignore_errors=True,
)
assert results[0].rc != 0
assert "could not select device driver" in results[0].stderr, results[0].stderr


# 3. Force installation on non-GPU node
d = en.Docker(
    agent=roles["nogpu"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
    nvidia_toolkit=True,
)
d.deploy()

# Check on non-GPU node, it should fail with another error
results = en.run_command(
    "docker run --rm --gpus all ubuntu:22.04 nvidia-smi",
    task_name="Nvidia support should be forced on normal node but still fail",
    roles=roles["nogpu"],
    ignore_errors=True,
)
assert results[0].rc != 0
assert "could not select device driver" not in results[0].stderr, results[0].stderr


# Release all Grid'5000 resources
provider.destroy()
