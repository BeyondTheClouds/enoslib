from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.provider.g5k import G5k

import os

provider_conf = {
    "job_name": "virtualbox",
    "walltime": "00:30:00",
    "dhcp": True,
    "resources": {
        "machines": [{
            "role": "control",
            "cluster": "griffon",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        },{
            "role": "compute",
            "cluster": "griffon",
            "nodes": 1,
            "primary_network": "n1",
            "secondary_networks": []
        }],
        "networks":[{
            "id": "n1",
            "roles": ["role1"],
            "type": "prod",
            "site": "nancy"
        }]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}
inventory = os.path.join(os.getcwd(), "hosts")
provider = Enos_vagrant()
roles, networks = provider.init(provider_conf)
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
