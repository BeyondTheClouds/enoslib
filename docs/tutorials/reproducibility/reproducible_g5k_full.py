import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# Check out http://snapshot.debian.org/
DEB_ARCHIVE_VERSION = "20221103"
ARCHIVE_URL = f"http://snapshot.debian.org/archive/debian/{DEB_ARCHIVE_VERSION}/"
SECURITY_URL = (
    f"http://snapshot.debian.org/archive/debian-security/{DEB_ARCHIVE_VERSION}/"
)
job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(
        job_type=["deploy"],
        env_name="debian10-min",
        job_name=job_name,
        walltime="00:50:00",
    )
    .add_machine(roles=["rennes"], cluster="paravance", nodes=1)
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Configure Debian repository
APT_CONF = f"""
deb [check-valid-until=no] {ARCHIVE_URL} buster main contrib non-free
deb [check-valid-until=no] {ARCHIVE_URL} buster-updates main contrib non-free
deb [check-valid-until=no] {ARCHIVE_URL} buster-backports main contrib non-free
# For bullseye and later, this has changed to e.g. "bullseye-security"
# instead of "buster/updates".
deb [check-valid-until=no] {SECURITY_URL} buster/updates main contrib non-free
"""
with en.actions(roles=roles) as a:
    a.copy(
        task_name="Configure APT",
        content=APT_CONF,
        dest="/etc/apt/sources.list",
    )

# Install packages
with en.actions(roles=roles) as a:
    a.apt(name=["htop", "iotop"], state="present", update_cache="yes")


# Release all Grid'5000 resources
provider.destroy()
