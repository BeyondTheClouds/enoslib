import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

CLUSTER = "paravance"

conf = en.G5kConf.from_settings(job_type=[], job_name=job_name).add_machine(
    roles=["control"], cluster=CLUSTER, nodes=2
)

provider = en.G5k(conf)
roles, networks = provider.init()


registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)

d = en.Docker(
    agent=roles["control"], bind_var_docker="/tmp/docker", registry_opts=registry_opts
)
d.deploy()
