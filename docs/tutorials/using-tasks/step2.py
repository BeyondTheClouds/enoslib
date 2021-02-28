import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "tiny",
            "number": 1,
        }, {
            "roles": ["compute"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"cidr": "192.168.40.0/24", "roles": ["mynetwork"]}]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "groups": ["control", "compute"]
}


@enostask(new=True)
def up(force=True, env=None, **kwargs):
    "Starts a new experiment"
    conf = VagrantConf.from_dictionnary(provider_conf)
    provider = Vagrant(conf)
    roles, networks = provider.init()
    roles = sync_info(roles, networks)
    env["roles"] = roles
    env["networks"] = networks


@enostask()
def emulate(env=None, **kwargs):
    roles = env["roles"]
    netem = NetemHTB(tc, roles=roles)
    netem.deploy()


@enostask()
def validate(env=None, **kwargs):
    roles = env["roles"]
    netem = NetemHTB(tc, roles=roles)
    netem.validate()


up()
emulate()
validate()
