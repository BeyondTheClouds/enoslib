import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

provider_conf = {
    "job_type": [],
    "job_name": job_name,
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "paravance",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
            {
                "roles": ["control", "compute"],
                "cluster": "paravance",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
        ],
        "networks": [
            {"id": "n1", "type": "prod", "roles": ["my_network"], "site": "rennes"}
        ],
    },
}

# claim the resources
conf = en.G5kConf.from_dictionary(provider_conf)
provider = en.G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuffs here
    # ...
except Exception as e:
    print(e)
finally:
    provider.destroy()
