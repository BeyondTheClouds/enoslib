import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(job_name=job_name)
    .add_machine(
        roles=["compute"],
        servers=["paravance-19.rennes.grid5000.fr"],
    )
    .add_machine(
        roles=["control"],
        servers=["parasilo-28.rennes.grid5000.fr"],
    )
    .add_machine(
        roles=["control"],
        cluster="paravance",
        nodes=1,
    )
)

provider = en.G5k(conf)
try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuff here
    # ...
except Exception as e:
    print(e)
finally:
    # Free all resources
    provider.destroy()
