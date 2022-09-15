import enoslib as en


en.init_logging()

provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["control", "compute"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}],
    }
}

# claim the resources
conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()
print(roles)
print(networks)

# destroy the boxes
provider.destroy()
