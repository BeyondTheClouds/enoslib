from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import Configuration

import logging

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
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
conf = Configuration.from_dictionnary(provider_conf)
provider = G5k(conf)
provider.init()

# destroy the reservation
provider.destroy()
