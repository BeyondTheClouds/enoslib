import logging
import os

from enoslib.api import sync_info
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration


logging.basicConfig(level=logging.DEBUG)
provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "address": "localhost",
                "alias": "test_machine",
                "extra": {"ansible_connection": "local"},
            }
        ],
        "networks": [
            {
                "roles": ["local"],
                "start": "172.17.0.0",
                "end": "172.17.255.255",
                "cidr": "172.17.0.0/16",
                "gateway": "172.17.0.1",
                "dns": "172.17.0.1",
            }
        ],
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
conf = Configuration.from_dictionary(provider_conf)
provider = Static(conf)

roles, networks = provider.init()
roles2 = sync_info(roles, networks)
# not network info attached to the nodes in roles
print(roles)
assert len(roles["control"][0].filter_addresses()) == 0
# some network info attached to the nodes in roles2
print(roles2)
assert len(roles2["control"][0].filter_addresses()) == 1
