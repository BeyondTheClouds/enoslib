import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)


# claim the resources
prod_network = G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=__file__,
                          job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_16",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(
        roles=["control"], cluster="parapluie", nodes=1, primary_network=prod_network
    )
    .finalize()
)


provider = G5k(conf)
roles, networks = provider.init()

# Retrieving subnet
subnet = [n for n in networks if "my_subnet" in n["roles"]]
logging.info(subnet)
# This returns the subnet information
# {
#    'roles': ['my_subnet'],
#    'start': '10.158.0.1',
#    'dns': '131.254.203.235',
#    'end': '10.158.3.254',
#    'cidr': '10.158.0.0/22',
#    'gateway': '10.159.255.254'
#    'mac_end': '00:16:3E:9E:03:FE',
#    'mac_start': '00:16:3E:9E:00:01',
# }

# destroy the reservation
provider.destroy()
