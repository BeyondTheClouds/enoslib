import logging
from pathlib import Path
import time

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
network = en.G5kNetworkConf(type="prod", roles=["my_network"], site="rennes")

conf = (
    en.G5kConf.from_settings(job_type="allow_classic_ssh", job_name=job_name)
    .add_network_conf(network)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["compute"],
        cluster="paravance",
        nodes=1,
        primary_network=network,
    )
    .finalize()
)

try:
    provider = en.G5k(conf)
    # Get actual resources
    roles, networks = provider.init()
    # open port 22 for host in the control group
    # add a firewall rule
    provider.fw_create(hosts=roles["control"], port=80)

    en.run("dhclient -6 br0", roles=roles["control"])
    en.run("apt update && apt install -y nginx", roles=roles["control"])
    result = en.run("ip -6 addr show dev br0", roles=roles["control"])

    print("-" * 80)
    print(f"Nginx available on IPV6: {result[0].stdout}")
    time.sleep(3600)
except Exception as e:
    print(e)
finally:
    # Clean everything
    # Clean the firewall rules (not mandatory since this will be removed when
    # the job finishes)
    provider.fw_delete()
    provider.destroy()