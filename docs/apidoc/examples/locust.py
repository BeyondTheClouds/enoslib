import enoslib as en

provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [{
            "roles": ["master"],
            "flavour": "tiny",
            "number": 1,
        }, {
            "roles": ["agent"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}]
    }
}

conf = en.VagrantConf.from_dictionnary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()

roles = en.sync_info(roles, networks)

locust = en.Locust(master=roles["master"][0],
           agents=roles["agent"])
locust.destroy()
locust.deploy()
locust.run_headless("expe", density=5, users=10, spawn_rate=1, run_time=20)
locust.backup()
