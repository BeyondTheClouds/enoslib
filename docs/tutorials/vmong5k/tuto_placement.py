import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.INFO)

job_name = Path(__file__).name

CLUSTER = "parasilo"
SITE = "rennes"


prod_network = G5kNetworkConf(
    id="n1",
    type="prod",
    roles=["my_network"],
    site=SITE)
conf = (
    G5kConf
    .from_settings(
        job_type="allow_classic_ssh",
        job_name=job_name
    )
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_22",
        roles=["my_subnet"],
        site=SITE
    )
    .add_machine(
        roles=["role1"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["role2"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
 )

provider = G5k(conf)
roles, networks = provider.init()
roles = discover_networks(roles, networks)

# Retrieving subnet
subnet = [n for n in networks if "my_subnet" in n["roles"]]
logging.info(subnet)

# We describe the VMs types and placement in the following
virt_conf = (
    VMonG5kConf
    .from_settings(image="/grid5000/virt-images/debian9-x64-std.qcow2")
    # Starts some vms on a single role
    # Here that means start the VMs on a single machine
    .add_machine(
        roles=["vms"],
        number=16,
        undercloud=roles["role1"]
    )
    .finalize()
)

# Start them
vmroles, networks = start_virtualmachines(virt_conf, subnet)
print(vmroles)
print(networks)
