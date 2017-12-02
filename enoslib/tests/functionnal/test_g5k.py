from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.infra.enos_g5k.provider import G5k

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
provider = G5k(provider_conf)
roles, networks = provider.init()
generate_inventory(roles, networks, inventory, check_networks=True)
emulate_network(roles, inventory, tc)
validate_network(roles, inventory)
