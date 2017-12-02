from enoslib.task import enostask
from docopt import docopt

import json
import os
import sys

PWD = os.getcwd()
def create_previous_xp(exp_name):
    env_dir = os.path.join(PWD, exp_name)
    if not os.path.exists(env_dir):
        os.mkdir(exp_name)
    with open(os.path.join(exp_name, "env"), "w") as f:
        f.write(json.dumps({"previous_exp": "this is from %s" % exp_name}))


@enostask(new=True)
def exp1(env=None, **kwargs):
    print("exp1 environment : %s" % env)


if __name__ == '__main__':
    s = """
    usage: test_enostask_docopt.py [-e ENV|--env=ENV]

    Get resources and install the docker registry.
    Options:
      -e ENV --env=ENV     Path to the environment directory. You should
               use this option when you want to link to a specific
               experiment. Do not specify it in other cases.
    """
    create_previous_xp("exp1")
    exp1(**docopt(s))
