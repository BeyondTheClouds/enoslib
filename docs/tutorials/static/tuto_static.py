import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)

# Use existing resources
conf = (
    StaticConf()
    .add_machine(
        roles=["control"], address="192.168.42.245", alias="static-0", user="root"
    )
    .add_machine(
        roles=["compute"], address="192.168.42.244", alias="static-1", user="root"
    )
    .add_network(
        roles=["mynetwork"],
        cidr="192.168.42.0/24",
        start="192.168.42.100",
        end="192.168.42.200",
        gateway="192.168.42.1",
        dns="8.8.8.8",
    )
    .finalize()
)

provider = Static(conf)

roles, networks = provider.init()
print(roles)
print(networks)
