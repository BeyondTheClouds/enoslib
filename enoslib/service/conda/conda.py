import copy
from textwrap import dedent as _d
from typing import List, Optional, Any
import os

from enoslib.api import play_on, run_command
from ..service import Service
from enoslib.types import Host


import yaml

INSTALLER_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
WRAPPER_PREFIX = "/opt/enoslib_conda"
CONDA_PREFIX = "/opt/conda"


def conda_wrapper(env_name: str):
    return f"{WRAPPER_PREFIX}/bin/{env_name}"


def _get_env_name(env_file: str):
    env_name = ""
    with open(env_file, "r") as f:
        env = yaml.load(f)
        env_name = env["name"]
    return env_name


def shell_in_conda(p: play_on, cmd: str, **kwargs: Any):
    """Make sure conda is initialized before launching the shell command.

    Implementation-wise this will source /opt/conda/etc/profile.d/conda.sh
    prior to the shell commands cmd.
    """
    p.shell(
        (f"which conda || source {CONDA_PREFIX}/etc/profile.d/conda.sh;" f"{cmd}"),
        **kwargs,
    )


def create_wrapper_script(p: play_on, env_name: str):
    """Create a wrapper script for Ansible.

    This can be used as an python interpreter and
    let the execution be contained, somehow, in a conda env.
    """
    p.file(state="directory", dest=os.path.dirname(conda_wrapper(env_name)))
    p.copy(
        dest=conda_wrapper(env_name),
        content=_d(
            f"""#!/bin/bash -l
            set -ex
            which conda || source {CONDA_PREFIX}/etc/profile.d/conda.sh
            conda activate {env_name}
            python3 $@
            """
        ),
        mode="0755",
    )


def _inject_wrapper_script(env_name, **kwargs):
    kwds = copy.deepcopy(kwargs)
    kwds.pop("run_as", None)
    kwds.pop("become", None)
    with play_on(**kwds) as p:
        create_wrapper_script(p, env_name)


def conda_run_command(command: str, env_name: str, **kwargs: Any):
    """Wrapper around :py:func:`enoslib.api.run_command` that is conda aware.

    Args:
        command: The command to run
        env_name: An existing env_name in which the command will be run
    """
    # should run as root
    _inject_wrapper_script(env_name, **kwargs)
    extra_vars = kwargs.pop("extra_vars", {})
    extra_vars.update(ansible_python_interpreter=conda_wrapper(env_name))
    # we are now ready to run this
    return run_command(command, extra_vars=extra_vars, **kwargs)


class conda_play_on(play_on):
    def __init__(self, env_name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.conda_env = env_name
        self.extra_vars.update(ansible_python_interpreter=conda_wrapper(env_name))
        _inject_wrapper_script(env_name, **kwargs)


class Conda(Service):
    def __init__(
        self, *, nodes: List[Host],
    ):

        """Manage Conda on your nodes.

        This installs miniconda on the nodes (latest version). Optionaly it
        can also prepare an environment.

        Args:
            nodes: The list of the nodes to install conda on.

        Examples:

            .. literalinclude:: examples/conda.py
                :language: python
                :linenos:

        """
        self.nodes = nodes
        self._roles = {"nodes": self.nodes}

    def deploy(
        self,
        env_file: Optional[str] = None,
        env_name: str = "",
        packages: Optional[List[str]] = None,
    ):
        """Deploy a conda environment.

        Args:
            env_file: create an environment based on this file.
                      if specified the following arguments will be ignored.
            env_name: name of the environment to create (if env_file is absent).
            packages: list of packages to install in the environment named env_name.
        """
        if packages is None:
            packages = []
        with play_on(roles=self._roles) as p:
            p.apt(name="wget", state="present")
            p.shell(
                (
                    f"which conda || ls {CONDA_PREFIX}/bin/conda || "
                    f"(wget --quiet {INSTALLER_URL} -O ~/miniconda.sh && "
                    f"/bin/bash ~/miniconda.sh -b -p {CONDA_PREFIX} && "
                    "rm ~/miniconda.sh)"
                )
            )

            # Install the env if any and leave
            # Don't reinstall if it already exists
            if env_file is not None:
                # look for the env_name
                _env_name = _get_env_name(env_file)
                p.copy(src=env_file, dest="environment.yml")
                shell_in_conda(
                    p,
                    (
                        f"(conda env list | grep '^{_env_name}') || "
                        "conda env create -f environment.yml"
                    ),
                    executable="/bin/bash",
                )
                create_wrapper_script(p, _env_name)
                return

            # Install packages if any
            if env_name is not None and len(packages) > 0:
                shell_in_conda(
                    p,
                    f"conda create --yes --name={env_name} {' '.join(packages)}",
                    executable="/bin/bash",
                )
                create_wrapper_script(p, env_name)
            if env_name is None and len(packages) > 0:
                shell_in_conda(
                    p,
                    f"conda create --yes {' '.join(packages)}",
                    executable="/bin/bash",
                )
                create_wrapper_script(p, env_name)

    def destroy(self):
        """Not implemented."""
        pass

    def backup(self):
        """Not implemented."""
        pass


class Dask(Service):
    def __init__(
        self, scheduler: Host, worker: List[Host], env_file: Optional[str] = None
    ):
        """ Initializes a Dask cluster on the nodes.

        Args:
            scheduler: the scheduler host
            worker: the workers Hosts
            env_file: conda environment with you specific dependencies.
                      Dask should be present in this environment.

        Examples:

            .. literalinclude:: examples/dask.py
                :language: python
                :linenos:

        """
        self.scheduler = scheduler
        self.worker = worker
        self.env_file = env_file
        self.env_name = _get_env_name(env_file) if env_file is not None else "__dask__"
        self.conda = Conda(nodes=worker + [scheduler])
        self.roles = {"scheduler": [self.scheduler], "worker": self.worker}

    def deploy(self):
        # Handle the environment
        if self.env_file is None:
            # Simply dask
            self.conda.deploy(env_name="__dask__", packages=["dask"])
        else:
            self.conda.deploy(env_file=self.env_file)

        # Start Dask cluster
        with play_on(roles=self.roles) as p:
            p.apt(name="tmux", state="present")

        with play_on(pattern_hosts="scheduler", roles=self.roles) as p:
            shell_in_conda(
                p,
                (
                    "(tmux ls | grep dask-scheduler) ||"
                    f"( conda activate {self.env_name} &&"
                    "tmux new-session -s dask-scheduler -d 'exec dask-scheduler' )"
                ),
                executable="/bin/bash",
                display_name="Starting the dask scheduler",
            )
        s = self.scheduler.address
        cmd = f"tmux new-session -s dask-worker -d 'exec dask-worker tcp://{s}:8786'"
        with play_on(pattern_hosts="worker", roles=self.roles) as p:
            shell_in_conda(
                p,
                (
                    "(tmux ls | grep dask-worker) ||"
                    f"( conda activate {self.env_name} &&"
                    f"{cmd} )"
                ),
                executable="/bin/bash",
                display_name="Starting the dask worker",
            )

    def destroy(self):
        with play_on(pattern_hosts="scheduler", roles=self.roles) as p:
            p.shell(
                "tmux kill-session -t dask-scheduler || true",
                executable="/bin/bash",
                display_name="Killing the dask scheduler",
            )
        with play_on(pattern_hosts="worker", roles=self.roles) as p:
            p.shell(
                "tmux kill-session -t dask-worker || true",
                executable="/bin/bash",
                display_name="Killing the dask worker ",
            )
