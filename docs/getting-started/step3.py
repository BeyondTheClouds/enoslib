from enoslib.api import generate_inventory, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_vagrant.provider import Enos_vagrant

import os
import logging
logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "virtualbox",
    "user": "root",
    "box": "debian/jessie64",
    "resources": {
        "machines": [{
            "role": "control",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n2"]
        },{
            "role": "compute",
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n3"]
        }]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}


import click
@click.group()
def cli():
    pass


@cli.command()
@click.option("--force",is_flag=True, help="vagrant destroy and up")
@enostask(new=True)
def up(force, env=None, **kwargs):
    """Starts a new experiment using vagrant"""
    inventory = os.path.join(os.getcwd(), "hosts")
    provider = Enos_vagrant(provider_conf)
    roles, networks = provider.init(force_deploy=force)
    generate_inventory(roles, networks, inventory, check_networks=True)
    env["roles"] = roles
    env["networks"] = networks
    env["inventory"] = inventory


@cli.command()
@enostask()
def emulate(env=None, **kwargs):
    """Emulates the network."""
    inventory = env["inventory"]
    roles = env["roles"]
    emulate_network(roles, inventory, tc)


@cli.command()
@enostask()
def validate(env=None, **kwargs):
    """Validates the network constraints."""
    inventory = env["inventory"]
    roles = env["roles"]
    validate_network(roles, inventory)


if __name__ == '__main__':
    cli()
