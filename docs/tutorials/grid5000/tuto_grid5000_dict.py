import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

provider_conf = {
    "job_name": job_name,
    "job_type": ["deploy", "exotic"],
    "env_name": "debian11-nfs",
    "walltime": "0:30:00",
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "servan",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": ["n2"],
            },
            {
                "roles": ["control", "compute"],
                "cluster": "servan",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": ["n2"],
            },
        ],
        "networks": [
            {"id": "n1", "type": "kavlan", "roles": ["my_network"], "site": "grenoble"},
            {
                "id": "n2",
                "type": "kavlan",
                "roles": ["my_second_network"],
                "site": "grenoble",
            },
        ],
    },
}

conf = en.G5kConf.from_dictionary(provider_conf)
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()
# Do your stuff
# ...


# Release all Grid'5000 resources
provider.destroy()
