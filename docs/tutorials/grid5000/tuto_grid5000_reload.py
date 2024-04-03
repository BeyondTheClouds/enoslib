import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

lille_net = en.G5kNetworkConf(type="kavlan", roles=["lille"], site="lille")

conf = (
    en.G5kConf.from_settings(
        job_type=["deploy"],
        env_name="debian11-nfs",
        job_name=job_name,
        walltime="0:30:00",
    )
    .add_network_conf(lille_net)
    .add_machine(roles=["nantes"], cluster="ecotype", nodes=1)
    .add_machine(
        roles=["lille"], cluster="chiclet", nodes=1, secondary_networks=[lille_net]
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
