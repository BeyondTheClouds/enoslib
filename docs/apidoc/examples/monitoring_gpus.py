import enoslib as en

import logging

logging.basicConfig(level=logging.INFO)


# They have GPU in lille !
CLUSTER = "chifflet"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)


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
                 nodes=1,
                 primary_network=network)\
    .add_machine(roles=["compute"],
                 cluster=CLUSTER,
                 nodes=1,
                 primary_network=network)\
    .finalize()

provider = en.G5k(conf)
roles, networks = provider.init()

# The Docker service knows how to deploy nvidia docker runtime
d = en.Docker(agent=roles["control"] + roles["compute"])
d.deploy()

# The Monitoring service knows how to use this specific runtime
m = en.TIGMonitoring(collector=roles["control"][0],
                     agent=roles["compute"],
                     ui=roles["control"][0])
m.deploy()

ui_address = roles["control"][0].address
print("The UI is available at http://%s:3000" % ui_address)
print("user=admin, password=admin")

import json
import time
import requests

# waiting a bit for some metrics to come on
# and query influxdb
collector_address = roles["control"][0].address
time.sleep(10)
with en.G5kTunnel(collector_address, 8086) as (local_address, local_port, tunnel):
    url = f"http://{local_address}:{local_port}/query"
    q = 'SELECT mean("temperature_gpu") FROM "nvidia_smi" WHERE time > now() - 5m GROUP BY time(1m), "index", "name", "host"'
    r = requests.get(url, dict(db="telegraf", q=q))
    print(json.dumps(r.json(), indent=4))