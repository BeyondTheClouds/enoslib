import enoslib as en

en.init_logging()

provider_conf = {
    "backend": "libvirt",
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
    },
}

conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)


result = en.run_command("date", roles=roles)
print(result)

# use a list of Hosts
result = en.run_command("date", roles=roles["control1"])
print(result)

# use a single Hosts
result = en.run_command("date", roles=roles["control1"][0])
print(result)

# filter hosts using a pattern
result = en.run_command("date", pattern_hosts="control*", roles=roles)
print(result)

# async tasks / will run in detached mode
result = en.run_command("date", roles=roles, background=True)
print(result)
