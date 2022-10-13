import logging
from pathlib import Path

import enoslib as en


en.init_logging(level=logging.DEBUG)


job_name = Path(__file__).name

provider_conf = {
    "job_name": job_name,
    "job_type": ["deploy"],
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "grisou",
                "nodes": 1,
                "primary_network": "n1",
            },
            {
                "roles": ["control", "compute"],
                "cluster": "grisou",
                "nodes": 1,
                "primary_network": "n1",
            },
        ],
        "networks": [
            {
                "id": "n1",
                "type": "kavlan",
                "roles": ["my_second_network"],
                "site": "nancy",
            },
        ],
    },
}

conf = en.G5kConf.from_dictionary(provider_conf)
provider = en.G5k(conf)

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
