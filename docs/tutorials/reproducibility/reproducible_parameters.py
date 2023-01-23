import logging
import sys
from pathlib import Path

import yaml

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# Parse parameters
params_file = sys.argv[1]
with open(params_file) as f:
    parameters = yaml.safe_load(f)

conf = en.G5kConf().from_settings(
    job_type=["deploy"],
    job_name=job_name,
    env_name=parameters["g5k_env"],
    walltime=parameters["g5k_walltime"],
)

# Add machines from parameters
for machine in parameters["g5k"]:
    conf = conf.add_machine(**machine)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Install packages
with en.actions(roles=roles) as a:
    a.apt(name=["htop", "iotop"], state="present", update_cache="yes")

# Do something with the parameters
print("Garage version:", parameters["garage_version"])
print("Garage metadata directory:", parameters["garage_metadata_dir"])


# Release all Grid'5000 resources
provider.destroy()
