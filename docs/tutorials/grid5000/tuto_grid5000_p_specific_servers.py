import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

kavlan_global = en.G5kNetworkConf(type="kavlan-global", roles=["private"], site="lille")

conf = (
    en.G5kConf()
    .from_settings(
        job_type=["deploy"],
        env_name="debian11-nfs",
        job_name=job_name,
        walltime="00:33:00",
    )
    .add_network_conf(kavlan_global)
    .add_machine(
        roles=["control"],
        servers=["paranoia-2.rennes.grid5000.fr"],
        secondary_networks=[kavlan_global],
    )
    .add_machine(
        roles=["control"],
        servers=["parasilo-28.rennes.grid5000.fr"],
        secondary_networks=[kavlan_global],
    )
    .add_machine(
        roles=["compute"],
        cluster="chifflot",
        nodes=1,
        secondary_networks=[kavlan_global],
    )
)

provider = en.G5k(conf)
try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuffs here
    # ...
except Exception as e:
    print(e)
finally:
    # destroy the reservation
    provider.destroy()
