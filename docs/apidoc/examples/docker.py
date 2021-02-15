import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)

conf = VagrantConf()\
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
provider = Vagrant(conf)
roles, networks = provider.init()

# generate an inventory compatible with ansible
roles = sync_info(roles, networks)

docker = Docker(registry=roles["control"], agent=roles["compute"])
docker.deploy()
docker.backup()
docker.destroy()

# destroy the boxes
provider.destroy()
