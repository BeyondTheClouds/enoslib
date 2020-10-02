from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration, NetworkConfiguration

import logging
import os

logging.basicConfig(level=logging.DEBUG)


# claim the resources
prod_rennes = NetworkConfiguration(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
prod_lille = NetworkConfiguration(
    id="n2", type="prod", roles=["my_network"], site="lille"
)
kavlan_global = NetworkConfiguration(
    id="n3", type="kavlan-global", roles=["private"], site="lille"
)

conf = (
    Configuration.from_settings(job_name="test-enoslib", walltime="00:33:00")
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

provider = G5k(conf)
roles, networks = provider.init()

# destroy the reservation
provider.destroy()
