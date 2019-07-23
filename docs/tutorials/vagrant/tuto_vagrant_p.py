from enoslib.service.monitoring import Monitoring
from enoslib.api import generate_inventory, discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

conf = Configuration()\
       .add_machine(roles=["control"],
                    flavour="tiny",
                    number=1)\
       .add_machine(roles=["control", "compute"],
                    flavour="tiny",
                    number=1)\
        .add_network(roles=["mynetwork"],
                      cidr="192.168.42.0/24")\
       .finalize()

# claim the resources
provider = Enos_vagrant(conf)
roles, networks = provider.init()


# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# generate an inventory compatible with ansible
discover_networks(roles, networks)
generate_inventory(roles, networks, inventory, check_networks=True)

m = Monitoring(collector=roles["compute"], agent=roles["control"], ui=roles["compute"])
m.deploy()
m.backup()
m.destroy()

# destroy the boxes
# provider.destroy()
