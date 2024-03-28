import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(job_name=job_name, walltime="0:10:00")
    .add_machine(
        roles=["compute"],
        servers=["paravance-19.rennes.grid5000.fr", "paravance-20.rennes.grid5000.fr"],
    )
    .add_machine(
        roles=["compute"],
        servers=[f"parasilo-{i}.rennes.grid5000.fr" for i in range(10, 20)],
        nodes=3,
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
