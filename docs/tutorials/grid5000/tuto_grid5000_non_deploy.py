import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

provider_conf = {
    "job_type": "allow_classic_ssh",
    "job_name": job_name,
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "parapluie",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
            {
                "roles": ["control", "compute"],
                "cluster": "parapluie",
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
conf = G5kConf.from_dictionnary(provider_conf)
provider = G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuffs here
    # ...
except Exception as e:
    print(e)
finally:
    provider.destroy()

