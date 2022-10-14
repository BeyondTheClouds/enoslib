import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name)
    .add_machine(roles=["groupA"], cluster="paravance", nodes=1)
    .add_machine(roles=["groupB"], cluster="parasilo", nodes=1)
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuff here
    # ...
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
