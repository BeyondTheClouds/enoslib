from ipaddress import IPv4Network, IPv6Network
from enoslib import *

import logging

logging.basicConfig(level=logging.INFO)

# claim the resources
conf = G5kConf.from_settings(job_type="allow_classic_ssh",
                                   job_name="test-non-deploy")
network = G5kNetworkConf(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site="rennes")
conf.add_network_conf(network)\
    .add_machine(roles=["control"],
                 cluster="paravance",
                 nodes=1,
                 primary_network=network)\
    .add_machine(roles=["compute"],
                 cluster="paravance",
                 nodes=1,
                 primary_network=network)\
    .finalize()

provider = G5k(conf)
roles, networks = provider.init()

run_command("dhclient -6 br0", roles=roles)
roles = sync_network_info(roles, networks)

network = [n for n in networks if isinstance(n.network, IPv6Network)]
m = TIGMonitoring(collector=roles["control"][0], agent=roles["compute"], ui=roles["control"][0], networks=network)
m.destroy()
m.deploy()

ui_address = roles["control"][0].address
print("The UI is available at http://%s:3000" % ui_address)
print("user=admin, password=admin")