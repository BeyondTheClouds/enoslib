from enoslib.infra.enos_distem.provider import Distem
from enoslib.infra.enos_distem.configuration import Configuration

import logging
import os

logging.basicConfig(level=logging.DEBUG)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_name="wip-distem")\
    .add_machine(roles=["compute", "coordinator"],
                 cluster="paravance",
                 number=1,
                 flavour="tiny")\
    .add_machine(roles=["controller"],
                 cluster="paravance",
                 number=1,
                 flavour="tiny")\
    .finalize()
provider = Distem(conf)

roles, networks = provider.init()
print(roles)
print(networks)
