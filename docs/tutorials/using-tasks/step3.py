from enoslib.api import check_networks, emulate_network, validate_network
from enoslib.task import enostask
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging
logging.basicConfig(level=logging.INFO)

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavor": "tiny",
            "number": 1,
            "networks": ["n1", "n2"]
        },{
            "roles": ["compute"],
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
    conf = Configuration.from_dictionnary(provider_conf)
    provider = Enos_vagrant(conf)
    roles, networks = provider.init(force_deploy=force)
    check_networks(roles, networks)
    env["roles"] = roles
    env["networks"] = networks


@cli.command()
@enostask()
def emulate(env=None, **kwargs):
    """Emulates the network."""
    roles = env["roles"]
    emulate_network(roles, tc)


@cli.command()
@enostask()
def validate(env=None, **kwargs):
    """Validates the network constraints."""
    roles = env["roles"]
    validate_network(roles)


if __name__ == '__main__':
    cli()
