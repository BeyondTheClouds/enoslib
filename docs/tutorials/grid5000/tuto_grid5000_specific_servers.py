import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(job_name=job_name, walltime="0:10:00")
    .add_machine(
        roles=["compute"],
        servers=["paravance-19.rennes.grid5000.fr"],
    )
    .add_machine(
        roles=["compute"],
        servers=["parasilo-28.rennes.grid5000.fr"],
    )
    .add_machine(
        roles=["control"],
        cluster="paravance",
        nodes=1,
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
