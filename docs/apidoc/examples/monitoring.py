from enoslib.service import Monitoring
from enoslib.api import discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging


logging.basicConfig(level=logging.INFO)

conf = Configuration()\
       .add_machine(roles=["control"],
                    flavour="tiny",
                    number=1)\
       .add_machine(roles=["compute"],
                    flavour="tiny",
                    number=1)\
        .add_network(roles=["mynetwork"],
                      cidr="192.168.42.0/24")\
       .finalize()

# claim the resources
provider = Enos_vagrant(conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
discover_networks(roles, networks)

m = Monitoring(collector=roles["control"], agent=roles["compute"], ui=roles["control"])
m.deploy()

ui_address = roles["control"][0].extra["mynetwork_ip"]
print("The UI is available at http://%s:3000" % ui_address)
print("user=admin, password=admin")

m.backup()
m.destroy()

# destroy the boxes
provider.destroy()
