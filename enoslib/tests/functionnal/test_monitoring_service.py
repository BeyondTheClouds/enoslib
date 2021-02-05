import logging
import os

from enoslib.api import sync_network_info
from enoslib.service import TIGMonitoring
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
conf = Configuration.from_dictionnary(provider_conf)
provider = Static(conf)

roles, networks = provider.init()

roles = sync_network_info(roles, networks)

m = TIGMonitoring(collector=roles["control"][0], agent=roles["control"], ui=roles["control"][0])
m.deploy()
m.backup()
# test whether the backup is ok...
m.destroy()
