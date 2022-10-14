import logging
from pathlib import Path

import enoslib as en
from enoslib.service.emul.utils import _validate


logging.basicConfig(level=logging.INFO)

job_name = Path(__file__).name

# claim the resources
conf = en.G5kConf.from_settings(job_type=[], job_name=job_name).add_machine(
    roles=["control"], cluster="chiclet", nodes=8
)


provider = en.G5k(conf)
roles, networks = provider.init()

_validate(roles, "_tmp_enos", [h.address for h in roles["control"]])
provider.destroy()
