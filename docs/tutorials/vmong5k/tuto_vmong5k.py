from enoslib.service.docker.docker import Docker
from enoslib.api import discover_networks, play_on
from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.DEBUG)

# claim the resources
conf = (
    Configuration
    .from_settings(job_name="tuto-vmong5k", gateway=True)
    .add_machine(
        roles=["docker", "compute"],
        cluster="parapluie",
        number=1,
        flavour_desc={
            "core": 4,
            "mem": 4096
        }
    )
    .add_machine(
        roles=["docker", "controller"],
        cluster="parapluie",
        number=3,
        flavour="tiny"
    )
    .finalize()
)


provider = VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)

# install docker on the nodes
# bind /var/lib/docker to /tmp/docker to gain some places
docker = Docker(agent=roles["docker"], bind_var_docker="/tmp/docker")
docker.deploy()

# start containers.
# Here on all nodes
with play_on(pattern_hosts="*", roles=roles) as p:
    p.docker_container(
        name="mycontainer",
        image="nginx",
        ports=["80:80"],
        state="started",
    )