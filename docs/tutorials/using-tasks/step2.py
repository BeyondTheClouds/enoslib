from enoslib.api import emulate_network, validate_network, check_networks
from enoslib.task import enostask
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import os

    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        },{
            "roles": ["compute"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        }]
    }
}


tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}


@enostask(new=True)
def up(force=True, env=None, **kwargs):
    "Starts a new experiment"
    inventory = os.path.join(os.getcwd(), "hosts")
    conf = Configuration.from_dictionnary(provider_conf)
    provider = Enos_vagrant(conf)
    roles, networks = provider.init()
    check_networks(roles, networks)
    env["roles"] = roles
    env["networks"] = networks


@enostask()
def emulate(env=None, **kwargs):
    roles = env["roles"]
    emulate_network(roles, tc)


@enostask()
def validate(env=None, **kwargs):
    roles = env["roles"]
    validate_network(roles)

up()
emulate()
validate()
