from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.INFO)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_name="tuto-vmong5k")\
    .add_machine(roles=["control"],
                 cluster="parapluie",
                 number=3,
                 flavour="large")\
    .add_machine(roles=["compute"],
                 cluster="parapluie",
                 number=100,
                 flavour="tiny")\
    .finalize()
provider = VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)
