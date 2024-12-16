import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# claim the resources
conf = (
    en.VMonG5kConf.from_settings(job_name=job_name)
    .add_machine(
        roles=["docker", "compute"],
        cluster="paradoxe",
        number=5,
        flavour_desc={"core": 1, "mem": 1024},
    )
    .add_machine(
        roles=["docker", "control"], cluster="paradoxe", number=1, flavour="large"
    )
)

provider = en.VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)

en.wait_for(roles)

# install docker on the nodes
registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)
# bind /var/lib/docker to /tmp/docker to gain some disk space
docker = en.Docker(
    agent=roles["docker"], bind_var_docker="/tmp/docker", registry_opts=registry_opts
)
docker.deploy()

# start containers.
# Here on all nodes
with en.actions(roles=roles) as a:
    a.docker_container(
        name="mycontainer",
        image="nginx",
        ports=["80:80"],
        state="started",
    )


# Release all Grid'5000 resources
provider.destroy()
