import logging
from pathlib import Path

import enoslib as en

en.init_logging()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_machine(
        roles=["paris", "vm"],
        cluster="paravance",
        nodes=1,
    )
    .add_machine(
        roles=["berlin", "vm"],
        cluster="paravance",
        nodes=1,
    )
    .add_machine(
        roles=["londres", "vm"],
        cluster="paravance",
        nodes=1,
    )
)
provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)

# Building the network constraints
emulation_conf = {
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "except": [],
    "constraints": [
        {"src": "paris", "dst": "londres", "symmetric": True, "delay": "10ms"}
    ],
}

logging.info(emulation_conf)

netem = en.NetemHTB.from_dict(emulation_conf, roles, networks)
netem.deploy()
netem.validate()
# netem.destroy()
