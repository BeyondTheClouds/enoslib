from pathlib import Path
import time

import enoslib as en

en.init_logging()


CLUSTER = "parasilo"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

# claim the resources
network = en.G5kNetworkConf(type="prod", roles=["my_network"], site=SITE)
conf = (
    en.G5kConf.from_settings(job_type="allow_classic_ssh", job_name="dstat")
    .add_network_conf(network)
    .add_machine(roles=["control"], cluster=CLUSTER, nodes=2, primary_network=network)
    .finalize()
)

provider = en.G5k(conf)
roles, networks = provider.init()

with en.actions(roles=roles["control"]) as a:
    a.apt(name="stress", state="present")

# Start a capture
# - for the duration of the commands
with en.Dstat(nodes=roles) as d:
    time.sleep(5)
    en.run("stress --cpu 4 --timeout 10", roles)
    time.sleep(5)


# sns.lineplot(data=result, x="epoch", y="usr", hue="host", markers=True, style="host")
# plt.show()
