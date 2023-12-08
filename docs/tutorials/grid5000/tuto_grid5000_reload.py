import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

nancy_net = en.G5kNetworkConf(type="kavlan", roles=["nancy"], site="nancy")
rennes_net = en.G5kNetworkConf(type="kavlan", roles=["rennes"], site="rennes")

conf = (
    en.G5kConf.from_settings(
        job_type=["deploy"],
        env_name="debian11-nfs",
        job_name=job_name,
        walltime="0:30:00",
    )
    .add_network_conf(nancy_net)
    .add_network_conf(rennes_net)
    .add_machine(
        roles=["nancy"], cluster="gros", nodes=1, secondary_networks=[nancy_net]
    )
    .add_machine(
        roles=["rennes"], cluster="paravance", nodes=1, secondary_networks=[rennes_net]
    )
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

en.run_command("uname -a", roles=roles)

# Reload
provider = en.G5k(conf)
roles, networks = provider.init()

en.run_command("uname -a", roles=roles)

# Release all Grid'5000 resources
provider.destroy()
