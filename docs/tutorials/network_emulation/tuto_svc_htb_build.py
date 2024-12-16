import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_machine(roles=["paris"], cluster="parasilo", nodes=1)
    .add_machine(roles=["berlin"], cluster="parasilo", nodes=1)
    .add_machine(roles=["londres"], cluster="parasilo", nodes=1)
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
