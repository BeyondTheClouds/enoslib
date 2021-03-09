import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

CLUSTER = "paravance"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)
# claim the resources
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)

conf = (
    en.G5kConf.from_settings(job_type="allow_classic_ssh", job_name=job_name)
    .add_network_conf(network)
    .add_machine(roles=["control"], cluster=CLUSTER, nodes=2, primary_network=network)
    .finalize()
)

provider = en.G5k(conf)
roles, networks = provider.init()


registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)

d = en.Docker(agent=roles["control"], registry_opts=registry_opts)
d.deploy()
