import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

provider_conf = {
    "job_name": job_name,
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "grisou",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": ["n2"],
            },
            {
                "roles": ["control", "compute"],
                "cluster": "grisou",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": ["n2"],
            },
        ],
        "networks": [
            {"id": "n1", "type": "kavlan", "roles": ["my_network"], "site": "nancy"},
            {
                "id": "n2",
                "type": "kavlan",
                "roles": ["my_second_network"],
                "site": "nancy",
            },
        ],
    },
}

conf = G5kConf.from_dictionnary(provider_conf)
provider = G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()
    # Do your stuffs
    # ...
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
