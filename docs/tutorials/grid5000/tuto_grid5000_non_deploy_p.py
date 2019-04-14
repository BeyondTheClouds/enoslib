from enoslib.api import generate_inventory
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import (Configuration,
                                                  NetworkConfiguration)

import logging
import os

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
                 nodes=1,
                 primary_network=network)\
    .add_machine(roles=["control", "network"],
                 cluster="paravance",
                 nodes=1,
                 primary_network=network)\
    .finalize()


try:
    provider = G5k(conf)

    roles, networks = provider.init()

    # generate an inventory compatible with ansible
    generate_inventory(roles, networks, inventory, check_networks=True)
finally:
    # destroy the reservation
    provider.destroy()
