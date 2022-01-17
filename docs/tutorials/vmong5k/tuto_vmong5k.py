import logging
from pathlib import Path

import enoslib as en


logging.basicConfig(level=logging.INFO)

job_name = Path(__file__).name

# claim the resources
conf = (
    en.VMonG5kConf
    .from_settings(job_name=job_name, gateway=True)
    .add_machine(
        roles=["docker", "compute"],
        cluster="paravance",
        number=3,
        flavour_desc={
            "core": 1,
            "mem": 1024
        }
    )
    .add_machine(
        roles=["docker", "controller"],
        cluster="paravance",
        number=3,
        flavour="tiny"
    )
    .finalize()
)


provider = en.VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)

en.wait_for(roles)
# install docker on the nodes
# bind /var/lib/docker to /tmp/docker to gain some places
docker = en.Docker(agent=roles["docker"], bind_var_docker="/tmp/docker")
docker.deploy()

# start containers.
# Here on all nodes
with en.actions(pattern_hosts="*", roles=roles) as a:
    a.docker_container(
        name="mycontainer",
        image="nginx",
        ports=["80:80"],
        state="started",
    )