from enoslib import *

provider_conf = {
    "backend": "libvirt",
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

roles = sync_info(roles, networks)

l = Locust(master=roles["master"],
           agents=roles["agent"])

l.deploy()
l.run_with_ui('expe')
