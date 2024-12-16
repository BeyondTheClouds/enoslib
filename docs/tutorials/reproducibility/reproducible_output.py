import logging
import os
import sys
from datetime import datetime
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

# Determine output dir: name of parameter file + date
current_date = datetime.isoformat(datetime.utcnow(), timespec="seconds")
params_name = Path(params_file).stem
output_dir = Path(__file__).parent / f"{params_name}_{current_date}"
os.mkdir(output_dir)

# Configure logging to copy everything to a file
handler = logging.FileHandler(output_dir / "logs")
formatter = logging.Formatter(
    fmt="%(asctime)s  %(name)-24s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logging.getLogger("").addHandler(handler)
# Also add a local logger
logger = logging.getLogger(job_name)


# Log parameters
logger.info("Experiment parameters: %s", parameters)

conf = (
    en.G5kConf()
    .from_settings(job_name=job_name, walltime="0:10:00")
    .add_machine(roles=["dummy"], cluster="parasilo", nodes=1)
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Perform your experiment

# Store output
with open(output_dir / "output.txt", "w") as f:
    f.write("Example output\n")


# Release all Grid'5000 resources
provider.destroy()
