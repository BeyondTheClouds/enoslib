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

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name


prod_network = en.G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_network_conf(prod_network)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=5, primary_network=prod_network
    )
    .finalize()
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Install docker
d = en.Docker(agent=roles["control"], bind_var_docker="/tmp/docker")
d.deploy()

# Start some containers
N = 25
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

# Get all the dockers running on the remote hosts
dockers = en.get_dockers(roles=roles)

# Build the network contraints to apply on the remote docker
# We assume here the interface name in docker to be eth0
sources = []
for idx, host in enumerate(dockers):
    delay = idx
    print(f"{host.alias} <-> {delay}")
    inbound = en.NetemOutConstraint(device="eth0", options=f"delay {delay}ms")
    outbound = en.NetemInConstraint(device="eth0", options=f"delay {delay}ms")
    sources.append(en.NetemInOutSource(host, constraints=[inbound, outbound]))


# The connection plugin used from here is docker protocol (not ssh). The
# Ansible implementation to support this protocol isn't as robust as SSH. For
# instance there's no automatic retries. Fortunately for such lack in the
# Ansible connection backend, enoslib provides an ``ansible_retries`` parameter
# that will keep retrying the whole set of tasks on the failed hosts until all
# hosts have succeeded.
with en.play_on(roles=dict(all=dockers), gather_facts=False, ansible_retries=5) as p:
    p.raw("apt update && apt install -y iproute2")

en.netem(sources, ansible_retries=5)
