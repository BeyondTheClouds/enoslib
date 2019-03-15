from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings()\
    .add_machine(roles=["control"],
                 address="192.168.42.245",
                 alias="static-0",
                 user="root")\
    .add_machine(roles=["compute"],
                 address="192.168.42.244",
                 alias="static-1",
                 user="root")\
    .add_network(roles=["mynetwork"],
                 cidr="192.168.42.0/24",
                 start="192.168.42.100",
                 end="192.168.42.200",
                 gateway="192.168.42.1",
                 dns="8.8.8.8")\
    .finalize()
provider = Static(conf)

roles, networks = provider.init()
print(roles)
print(networks)
