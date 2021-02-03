from enoslib import *

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

conf = VagrantConf.from_dictionnary(provider_conf)
provider = Vagrant(conf)
roles, networks = provider.init()

roles = sync_network_info(roles, networks)

l = Locust(master=roles["master"],
            agents=roles["agent"],
            network="r1")

l.deploy()
l.run_with_ui('expe')
ui_address = roles["master"][0].extra["r1_ip"]
print("LOCUST : The Locust UI is available at http://%s:8089" % ui_address)
