import logging
from pathlib import Path
import time

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


import enoslib as en

logging.basicConfig(level=logging.DEBUG)

CLUSTER = "parasilo"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

# claim the resources
conf = en.G5kConf.from_settings(job_type="allow_classic_ssh",
                                   job_name="test-non-deploy")
network = en.G5kNetworkConf(id="n1",
                               type="prod",
                               roles=["my_network"],
                               site=SITE)
conf.add_network_conf(network)\
    .add_machine(roles=["control"],
                 cluster=CLUSTER,
                 nodes=2,
                 primary_network=network)\
    .finalize()

provider = en.G5k(conf)
roles, networks = provider.init()

with en.actions(roles["control"]) as a:
    a.apt(name="stress", state="present")

# Start a capture
# - for the duration of the commands
with en.Dstat(nodes=roles["control"]) as d:
    time.sleep(5)
    en.run("stress --cpu 4 --timeout 10", roles["control"])
    time.sleep(5)
    backup_dir = d.backup_dir

# Create a dictionnary of (alias) -> list of pandas df
result = pd.DataFrame()
for host in roles["control"]:
    host_dir = backup_dir / host.alias
    csvs = host_dir.rglob("*.csv")
    for csv in csvs:
        df = pd.read_csv(csv, skiprows=5, index_col=False)
        df["host"] = host.alias
        df["csv"] = csv
        result = pd.concat([result, df], axis=0)

sns.lineplot(data=result, x="epoch", y="usr", hue="host", markers=True, style="host")
plt.show()