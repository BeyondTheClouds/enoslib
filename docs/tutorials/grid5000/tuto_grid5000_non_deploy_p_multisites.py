import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name)
    .add_machine(roles=["control"], cluster="paravance", nodes=1)
    .add_machine(roles=["control"], cluster="chiclet", nodes=1)
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
    # Clean everything
    provider.destroy()
