from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import (Configuration,
                                                  NetworkConfiguration)
from enoslib.service import Dstat

import logging
import os
import time

logging.basicConfig(level=logging.DEBUG)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_type="allow_classic_ssh",
                                   job_name="test-non-deploy")
network = NetworkConfiguration(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site="nancy")
conf.add_network_conf(network)\
    .add_machine(roles=["control"],
                 cluster="grisou",
                 nodes=2,
                 primary_network=network)\
    .finalize()

provider = G5k(conf)
roles, networks = provider.init()

m = Dstat(nodes=roles["control"])

m.deploy()

time.sleep(10)
m.destroy()
m.backup()


# destroy the boxes
# provider.destroy()
