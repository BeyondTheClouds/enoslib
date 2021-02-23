import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
conf = (
    VMonG5kConf
    .from_settings(job_name=job_name, gateway=True)
    .add_machine(
        roles=["docker", "compute"],
        cluster="parapluie",
        number=2,
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

wait_for(roles)
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