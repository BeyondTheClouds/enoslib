from enoslib.task import enostask

import click
import json
import os

@click.group()
def cli():
    pass

PWD = os.getcwd()
def create_previous_xp(exp_name):
    env_dir = os.path.join(PWD, exp_name)
    if not os.path.exists(env_dir):
        os.mkdir(exp_name)
    with open(os.path.join(exp_name, "env"), "w") as f:
        f.write(json.dumps({"previous_exp": "this is from %s" % exp_name}))

create_previous_xp("exp1")

@cli.command()
@click.option("--env", help="abs path to an existing exp (containing an env)")
@enostask(new=True)
def exp1(env=None, **kwargs):
    print("exp1 environment : %s" % env)


@cli.command()
@enostask()
def t1(env=None, **kwargs):
    print("From t1 : %s" % env)


if __name__ == '__main__':
    cli()
