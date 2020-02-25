from typing import List, Optional

from enoslib.api import play_on
from ..service import Service
from enoslib.types import Host

import yaml

INSTALLER_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"


def _get_env_name(env_file):
    env_name = ""
    with open(env_file, "r") as f:
        env = yaml.load(f)
        env_name = env["name"]
    return env_name


def shell_in_conda(p: play_on, cmd: str, **kwargs):
    """Make sure conda is initialized before launching the shell command.

    Implementation-wise this will source /opt/conda/etc/profile.d/conda.sh
    prior to the shell commands cmd.
    """
    p.shell(
        (
            "source /opt/conda/etc/profile.d/conda.sh;"
            f"{cmd}"
        ),
        **kwargs
    )


class Conda(Service):
    def __init__(
        self,
        *,
        nodes: List[Host],
    ):

        """Manage Conda on your nodes.

        This installs miniconda on the nodes (latest version). Optionaly it
        can also prepare an environment.

        Args:
            nodes: The list of the nodes to install conda on.
        """
        self.nodes = nodes
        self._roles = {"nodes": self.nodes}

    def deploy(self,
               env_file: Optional[str] = None,
               env_name: str = "",
               packages: Optional[List[str]] = None):
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
                    "ls /opt/conda/bin/conda || "
                    f"(wget --quiet {INSTALLER_URL} -O ~/miniconda.sh && "
                    "/bin/bash ~/miniconda.sh -b -p /opt/conda && "
                    "rm ~/miniconda.sh)"
                )
            )
            # Make sure bash session loads the conda environment
            # Note that on the CI, this isn't sufficient since we're using
            # local connection
            p.lineinfile(
                path="/root/.bashrc",
                line="source /opt/conda/etc/profile.d/conda.sh",
                state="present")

            # Install the env if any and leave
            # Don't reinstall if it already exists
            if env_file is not None:
                # look for the env_name
                _env_name = _get_env_name(env_file)
                p.copy(src=env_file, dest="requirements.yml")
                shell_in_conda(p,
                    (
                        f"(conda env list | grep '^{_env_name}') || "
                        "conda env create -f requirements.yml"
                    ),
                    executable="/bin/bash"
                )
                return

            # Install packages if any
            if env_name is not None and len(packages) > 0:
                shell_in_conda(
                    p,
                    f"conda create --yes --name={env_name} {' '.join(packages)}",
                    executable="/bin/bash")
            if env_name is None and len(packages) > 0:
                shell_in_conda(
                    p,
                    f"conda create --yes {' '.join(packages)}",
                    executable="/bin/bash")

    def destroy(self):
        """Not implemented."""
        pass

    def backup(self):
        """Not implemented."""
        pass


class Dask(Service):

    def __init__(self, scheduler: Host,
                 worker: List[Host],
                 env_file: Optional[str] = None):
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
            shell_in_conda(p,
                (
                    "(tmux ls | grep dask-scheduler) ||"
                    f"( conda activate {self.env_name} &&"
                    "tmux new-session -s dask-scheduler -d 'exec dask-scheduler' )"
                ),
                executable="/bin/bash",
                display_name="Starting the dask scheduler"
            )
        s = self.scheduler.address
        cmd = f"tmux new-session -s dask-worker -d 'exec dask-worker tcp://{s}:8786'"
        with play_on(pattern_hosts="worker", roles=self.roles) as p:
            shell_in_conda(p,
                (
                    "(tmux ls | grep dask-worker) ||"
                    f"( conda activate {self.env_name} &&"
                    f"{cmd} )"
                ),
                executable="/bin/bash",
                display_name="Starting the dask worker"
            )

    def destroy(self):
        with play_on(pattern_hosts="scheduler", roles=self.roles) as p:
            p.shell("tmux kill-session -t dask-scheduler || true",
                executable="/bin/bash",
                display_name="Killing the dask scheduler")
        with play_on(pattern_hosts="worker", roles=self.roles) as p:
            p.shell("tmux kill-session -t dask-worker || true",
                executable="/bin/bash",
                display_name="Killing the dask worker ")
