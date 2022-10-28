import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

provider_conf = {
    "job_name": job_name,
    "walltime": "0:10:00",
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "paravance",
                "nodes": 1,
            }
        ],
        "networks": [
            {
                "id": "not_linked_to_any_machine",
                "type": "slash_22",
                "roles": ["my_subnet"],
                "site": "rennes",
            },
        ],
    },
}

# claim the resources
conf = en.G5kConf.from_dictionary(provider_conf)
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Retrieving subnet
subnet = networks["my_subnet"][0]
logging.info(subnet.__dict__)
# This returns the subnet information:
# subnet.network -> IPv4Network('10.158.0.0/22')
# subnet.gateway -> IPv4Address('10.159.255.254')

# Do your stuff here
# ...


# Release all Grid'5000 resources
provider.destroy()
