import logging
import os

from enoslib.api import discover_networks
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration
from enoslib.service import Netem
from enoslib.task import enostask


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
    conf = Configuration.from_dictionnary(provider_conf)
    provider = Enos_vagrant(conf)
    roles, networks = provider.init(force_deploy=force)
    discover_networks(roles, networks)
    env["roles"] = roles
    env["networks"] = networks


@cli.command()
@enostask()
def emulate(env=None, **kwargs):
    """Emulates the network."""
    roles = env["roles"]
    netem = Netem(tc, roles=roles)
    netem.deploy()


@cli.command()
@enostask()
def validate(env=None, **kwargs):
    """Validates the network constraints."""
    roles = env["roles"]
    netem = Netem(tc, roles=roles)
    netem.validate()



if __name__ == '__main__':
    cli()
