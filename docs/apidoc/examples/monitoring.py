import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()


CLUSTER = "parasilo"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)
job_name = Path(__file__).name

# claim the resources
conf = en.G5kConf.from_settings(job_name=job_name, walltime="1:00:00", job_type=[])
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
conf.add_network_conf(network).add_machine(
    roles=["control"], cluster=CLUSTER, nodes=1, primary_network=network
).add_machine(
    roles=["compute"], cluster=CLUSTER, nodes=1, primary_network=network
).finalize()

provider = en.G5k(conf)
roles, networks = provider.init()

m = en.TIGMonitoring(
    collector=roles["control"][0], agent=roles["compute"], ui=roles["control"][0]
)
m.deploy()

ui_address = roles["control"][0].address
print("The UI is available at http://%s:3000" % ui_address)
print("user=admin, password=admin")
