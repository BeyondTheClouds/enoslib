from enoslib.api import play_on
from enoslib.infra.enos_distem.provider import Distem
from enoslib.infra.enos_distem.configuration import Configuration

import logging
import os


FORCE = False

logging.basicConfig(level=logging.DEBUG)

# path to the inventory
inventory = os.path.join(os.getcwd(), "hosts")

# claim the resources
conf = Configuration.from_settings(job_name="wip-distem",
                                   force_deploy=FORCE,
                                   image="file:///home/rolivo/public/distem-fs-jessie.tar.gz")\
    .add_machine(roles=["compute"],
                 cluster="parapide",
                 number=50,
                 flavour="tiny")\
    .add_machine(roles=["controller"],
                 cluster="parapluie",
                 number=1,
                 flavour="tiny")\
    .finalize()
provider = Distem(conf)

roles, networks = provider.init()

print(roles)
print(networks)

with play_on(roles=roles,gather_facts=False) as p:
    p.raw("date")
