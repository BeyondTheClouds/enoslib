import logging
from pathlib import Path
import time

import enoslib as en

en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name


conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name)
    .add_machine(roles=["control"], cluster="paravance", nodes=1)
    .add_machine(
        roles=["compute"],
        cluster="paravance",
        nodes=1,
    )
)

provider = en.G5k(conf)
try:
    # Get actual resources
    roles, networks = provider.init()
    # Open port 22 for host in the control group
    # Add a firewall rule (just during the time of the context)
    # Alternatively you can use provider.fw_create/fw_delete
    with provider.firewall(hosts=roles["control"], port=80):
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
    # provider.fw_delete()
    provider.destroy()
