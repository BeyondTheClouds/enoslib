import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
prod_rennes = en.G5kNetworkConf(type="prod", roles=["my_network"], site="rennes")
prod_lille = en.G5kNetworkConf(type="prod", roles=["my_network"], site="lille")
kavlan_global = en.G5kNetworkConf(
    id="n3", type="kavlan-global", roles=["private"], site="lille"
)

conf = (
    en.G5kConf()
    .from_settings(job_name=__file__, walltime="00:33:00")
    .add_network_conf(prod_rennes)
    .add_network_conf(prod_lille)
    .add_network_conf(kavlan_global)
    .add_machine(
        roles=["control"],
        servers=["paranoia-2.rennes.grid5000.fr"],
        primary_network=prod_rennes,
        secondary_networks=[kavlan_global],
    )
    .add_machine(
        roles=["control"],
        servers=["parasilo-28.rennes.grid5000.fr"],
        primary_network=prod_rennes,
        secondary_networks=[kavlan_global],
    )
    .add_machine(
        roles=["compute"],
        cluster="chifflot",
        nodes=1,
        primary_network=prod_lille,
        secondary_networks=[kavlan_global],
    )
    .finalize()
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
