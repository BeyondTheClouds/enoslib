import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

SITE = "rennes"
CLUSTER = "paravance"

private = en.G5kNetworkConf(type="kavlan", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        job_type=["deploy"],
        env_name="debian11-nfs",
        walltime="0:20:00",
    )
    .add_network_conf(private)
    .add_machine(
        roles=["server"],
        cluster=CLUSTER,
        nodes=1,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["client"],
        cluster=CLUSTER,
        nodes=1,
        secondary_networks=[private],
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
