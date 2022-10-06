import enoslib as en

en.init_logging()


provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["compute"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"cidr": "192.168.40.0/24", "roles": ["mynetwork"]}],
    },
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["control", "compute"],
}


@en.enostask(new=True)
def up(force=True, env=None, **kwargs):
    """Starts a new experiment"""
    conf = en.VagrantConf.from_dictionary(provider_conf)
    provider = en.Vagrant(conf)
    roles, networks = provider.init()
    roles = en.sync_info(roles, networks)
    env["roles"] = roles
    env["networks"] = networks


@en.enostask()
def emulate(env=None, **kwargs):
    roles = env["roles"]
    netem = en.NetemHTB(tc, roles=roles)
    netem.deploy()


@en.enostask()
def validate(env=None, **kwargs):
    roles = env["roles"]
    netem = en.NetemHTB(tc, roles=roles)
    netem.validate()


up()
emulate()
validate()
