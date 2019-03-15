from enoslib.api import play_on
from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration

import os

# Dummy functionnal test running inside a docker container

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "address": "localhost",
            "extra": {
                "ansible_connection": "local"
            }
        }],
        "networks": [{
            "roles": ["local"],
            "start": "172.17.0.0",
            "end": "172.17.255.255",
            "cidr": "172.17.0.0/16",
            "gateway": "172.17.0.1",
            "dns": "172.17.0.1",
        }]
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
conf = Configuration.from_dictionnary(provider_conf)
provider = Static(conf)

roles, networks = provider.init()

with play_on("all", roles=roles) as p:
    p.shell("date > /tmp/date")

with open("/tmp/date") as f:
    print(f.readlines(f))
