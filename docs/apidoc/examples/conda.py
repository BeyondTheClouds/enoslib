from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import (Configuration,
                                                  NetworkConfiguration)
from enoslib.service.conda import Conda, conda_run_command, conda_play_on
import logging
import os
import time

logging.basicConfig(level=logging.DEBUG)

# claim the resources
conf = Configuration.from_settings(job_type="allow_classic_ssh",
                                   job_name="conda")
network = NetworkConfiguration(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site="rennes")
conf.add_network_conf(network)\
    .add_machine(roles=["control"],
                 cluster="parapluie",
                 nodes=2,
                 primary_network=network)\
    .finalize()

provider = G5k(conf)
roles, networks = provider.init()

# let's provision a new env
m = Conda(nodes=roles["control"])
m.deploy(env_name="plop", packages=["dask"])

# make use of this environment new environment
r = conda_run_command("conda env export", "plop", roles=roles)
print(r)

# make use of an existing environment (somewhere in ~/miniconda3 most probably)
# this is practical because the env can be created on a shared filesystem
# ans use on all the nodes
r = conda_run_command("conda env export", "spark", roles=roles, run_as="msimonin")
print(r)

# run this in the new (local to the node) environment
with conda_play_on("plop", roles=roles) as p:
    p.shell("conda env export > /tmp/plop.env")
    p.fetch(src="/tmp/plop.env", dest="/tmp/plop.env")

# run this in a shared environment
with conda_play_on("spark", roles=roles, run_as="msimonin") as p:
    # launch a script that requires spark n'co
    p.shell("conda env export > /tmp/spark.env")
    p.fetch(src="/tmp/plop.env", dest="/tmp/spark.env")