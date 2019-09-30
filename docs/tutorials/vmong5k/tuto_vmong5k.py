from enoslib.api import discover_networks
from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.DEBUG)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_name="tuto-vmong5k")\
        .add_machine(roles=["compute"],
                 cluster="grisou",
                 number=1,
                 flavour="tiny")\
    .add_machine(roles=["controller"],
                 cluster="grisou",
                 number=3,
                 flavour="tiny")\
    .finalize()
provider = VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)
