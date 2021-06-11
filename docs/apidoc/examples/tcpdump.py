import logging
import time

import enoslib as en

logging.basicConfig(level=logging.INFO)


CLUSTER = "paravance"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)


# claim the resources
conf = en.G5kConf.from_settings(
    job_type="allow_classic_ssh", job_name="test-non-deploy"
)
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
conf.add_network_conf(network).add_machine(
    roles=["control"], cluster=CLUSTER, nodes=1, primary_network=network
).add_machine(
    roles=["control"], cluster=CLUSTER, nodes=1, primary_network=network
).finalize()

provider = en.G5k(conf)
roles, networks = provider.init()

roles = en.sync_info(roles, networks)

# start a capture
# - on all the interface configured on the my_network network
# - for the duration of the commands (here a simple sleep)
with en.TCPDump(hosts=roles["control"], networks=networks["my_network"]):
    time.sleep(10)

# pcap files are retrieved in the __enoslib__tcpdump__ directory
# - can be loaded in wireshark
# - manipulated with scappy ...
