from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import click
import os

provider_conf = {
    "backend": "virtualbox",
    "user": "root",
    "resources": {
        "machines": [{
            "role": "control",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1"]
        },{
            "role": "compute",
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
    provider = Enos_vagrant(provider_conf)
    roles, networks = provider.init()
    generate_inventory(roles, networks, inventory, check_networks=True)
    env["roles"] = roles
    env["networks"] = networks
    env["inventory"] = inventory


@enostask()
def emulate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    emulate_network(roles, inventory, tc)


@enostask()
def validate(env=None, **kwargs):
    inventory = env["inventory"]
    roles = env["roles"]
    validate_network(roles, inventory)

up()
emulate()
validate()
