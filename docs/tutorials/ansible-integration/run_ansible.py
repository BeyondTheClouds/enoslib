import enoslib as en

en.init_logging()


provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control1"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["control2"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}],
    }
}

conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()

result = en.run_ansible(["site.yml"], roles=roles)
print(result)
