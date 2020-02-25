from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import (Configuration,
                                                  NetworkConfiguration)
from enoslib.service import Conda, Dask

import logging
import os
import time

logging.basicConfig(level=logging.INFO)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_type="allow_classic_ssh",
                                   job_name="test-non-deploy")
network = NetworkConfiguration(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site="rennes")
conf.add_network_conf(network)\
    .add_machine(roles=["control"],
                 cluster="paravance",
                 nodes=2,
                 primary_network=network)\
    .finalize()

provider = G5k(conf)
roles, networks = provider.init()

m = Dask(scheduler=roles["control"][0],
         worker=roles["control"],
         env_file="./environment.yml")
m.deploy()

time.sleep(10)
m.destroy()

# destroy the boxes
# provider.destroy()
