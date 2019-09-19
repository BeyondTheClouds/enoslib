from enoslib.api import discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration
from enoslib.service import Locust

provider_conf = {
    "backend": "virtualbox",
    "resources": {
        "machines": [{
            "roles": ["master"],
            "flavour": "tiny",
            "number": 1,
        },{
            "roles": ["agent"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}]
    }
}

conf = Configuration.from_dictionnary(provider_conf)
provider = Enos_vagrant(conf)
roles, networks = provider.init()

discover_networks(roles, networks)

l = Locust(master=roles["master"],
            agents=roles["agent"],
            network="r1")

l.deploy()
l.run_with_ui('expe', 'expe/locustfile.py', targeted_hosts=(roles["master"] + roles["agent"]))
ui_address = roles["master"][0].extra["r1_ip"]
print("LOCUST : The Locust UI is available at http://%s:8089" % ui_address)