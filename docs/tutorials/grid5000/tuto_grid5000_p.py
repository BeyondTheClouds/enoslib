from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration

import logging
import os

logging.basicConfig(level=logging.INFO)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
network = NetworkConfiguration(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site="rennes")
second = NetworkConfiguration(id="n2",
                              type="kavlan",
                              roles=["my_network_2"],
                              site="rennes")
conf = Configuration.from_settings(job_name="_test-enoslib_")\
    .add_network_conf(network)\
    .add_network_conf(second)\
    .add_machine(roles=["control"],
                 cluster="paravance",
                 nodes=1,
                 primary_network=network,
                 secondary_networks=[second])\
    .add_machine(roles=["control", "compute"],
                 cluster="paravance",
                 nodes=1,
                 primary_network=network,
                 secondary_networks=[second])\
    .finalize()

provider = G5k(conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
generate_inventory(roles, networks, inventory, check_networks=True)

# destroy the reservation
provider.destroy()
