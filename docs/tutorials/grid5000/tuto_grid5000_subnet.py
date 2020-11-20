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
                "cluster": "parapluie",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            }
        ],
        "networks": [
            {"id": "n1", "type": "prod", "roles": ["my_network"], "site": "rennes"},
            {
                "id": "not_linked_to_any_machine",
                "type": "slash_22",
                "roles": ["my_subnet"],
                "site": "rennes",
            },
        ],
    }
}

# claim the resources
conf = G5kConf.from_dictionnary(provider_conf)
provider = G5k(conf)

try:
    # Get actual resources
    roles, networks = provider.init()

    # Retrieving subnet
    subnet = [n for n in networks if "my_subnet" in n["roles"]]
    logging.info(subnet)
    # This returns the subnet information
    # {
    #    'roles': ['my_subnet'],
    #    'start': '10.158.0.1',
    #    'dns': '131.254.203.235',
    #    'end': '10.158.3.254',
    #    'cidr': '10.158.0.0/22',
    #    'gateway': '10.159.255.254'
    #    'mac_end': '00:16:3E:9E:03:FE',
    #    'mac_start': '00:16:3E:9E:00:01',
    # }

    # Do your stuffs here
    # ...
except Exception as e:
    print(e)
finally:
    # Clean everything
    provider.destroy()
