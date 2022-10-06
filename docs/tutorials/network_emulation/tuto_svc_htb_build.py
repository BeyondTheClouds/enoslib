import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

prod_network = en.G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_network_conf(prod_network)
    .add_machine(
        roles=["paris"], cluster="paravance", nodes=1, primary_network=prod_network
    )
    .add_machine(
        roles=["berlin"], cluster="paravance", nodes=1, primary_network=prod_network
    )
    .add_machine(
        roles=["londres"], cluster="paravance", nodes=1, primary_network=prod_network
    )
    .finalize()
)
provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)


netem = en.NetemHTB()
(
    netem.add_constraints(
        src=roles["paris"],
        dest=roles["londres"],
        delay="10ms",
        rate="1gbit",
        symmetric=True,
    )
    .add_constraints(
        src=roles["paris"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symmetric=True,
    )
    .add_constraints(
        src=roles["londres"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symmetric=True,
    )
)
netem.deploy()
netem.validate()
# netem.destroy()
