import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "job_name": __file__,
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
    }
}

# claim the resources
conf = G5kConf.from_dictionnary(provider_conf)
provider = G5k(conf)
provider.init()

# destroy the reservation
provider.destroy()
