"""
Example that makes use of the DockerHost data structure.

This is an advanced example where
- docker containers will be started on g5k machines
- network emulation will be enforced between those docker containers by
reusing |enoslib| api functions.
"""

import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name


conf = (
    en.G5kConf.from_settings(job_name=job_name, walltime="0:30:00", job_type=[])
    .add_machine(roles=["control"], cluster="econome", nodes=2)
    .finalize()
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Install docker
registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)
d = en.Docker(
    agent=roles["control"], bind_var_docker="/tmp/docker", registry_opts=registry_opts
)
d.deploy()

# Start N containers on each G5K host (for a total of 2*N containers)
N = 4
with en.play_on(roles=roles) as p:
    p.raw("modprobe ifb")
    for i in range(N):
        p.docker_container(
            name=f"mydocker-{i}",
            image="ubuntu",
            state="started",
            command="sleep 10d",
            capabilities=["NET_ADMIN"],
        )

# Get all the docker containers running on all remote hosts
dockers = en.get_dockers(roles=roles)

# Build the network contraints to apply on the remote docker
# We assume here the interface name in docker to be eth0
sources = []
for idx, host in enumerate(dockers):
    delay = idx
    print(f"{host.alias} <-> {delay}ms")
    inbound = en.NetemOutConstraint(device="eth0", options=f"delay {delay}ms")
    outbound = en.NetemInConstraint(device="eth0", options=f"delay {delay}ms")
    sources.append(en.NetemInOutSource(host, constraints={inbound, outbound}))

# This requires the Docker client to be installed on the local machine.
# Also, it might not work well because SSH connections are handled by Docker.
# See https://gitlab.inria.fr/discovery/enoslib/-/issues/163 for discussion
with en.play_on(roles=dockers, gather_facts=False) as p:
    # We can't use the 'apt' module because python is not installed in containers
    p.raw("apt update && DEBIAN_FRONTEND=noninteractive apt install -qq -y iproute2")

en.netem(sources)
