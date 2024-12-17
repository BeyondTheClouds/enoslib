import logging
from pathlib import Path

import enoslib as en

en.init_logging(logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[], walltime="0:10:00")
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_16",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(roles=["control"], cluster="paradoxe", nodes=1)
)

provider = en.G5k(conf)

# Get actual resources

roles, networks = provider.init()


# Release all Grid'5000 resources
provider.destroy()
