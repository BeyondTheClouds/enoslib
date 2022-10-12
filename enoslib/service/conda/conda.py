import copy
from textwrap import dedent as _d
from typing import Iterable, List, Optional, Any
from itertools import chain
import os

from enoslib.api import actions, run
from enoslib.objects import Host, Roles
from ..service import Service


import yaml

INSTALLER_URL = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
WRAPPER_PREFIX = "/opt/enoslib_conda"
CONDA_PREFIX = "/opt/conda"


def _conda_wrapper(env_name: str):
    return f"{WRAPPER_PREFIX}/bin/{env_name}"


def _get_env_name(env_file: str):
    env_name = ""
    with open(env_file) as f:
        env = yaml.safe_load(f)
        env_name = env["name"]
    return env_name


def _shell_in_conda(p: actions, cmd: str, **kwargs: Any):
    """Make sure conda is initialized before launching the shell command.

    Implementation-wise this will source /opt/conda/etc/profile.d/conda.sh
    prior to the shell commands cmd.
    """
    p.shell(
        (f"which conda || source {CONDA_PREFIX}/etc/profile.d/conda.sh;" f"{cmd}"),
        **kwargs,
    )


def _create_wrapper_script(p: actions, env_name: str):
    """Create a wrapper script for Ansible.

    This can be used as a python interpreter and
    let the execution be contained, somehow, in a conda env.
    """
    p.file(state="directory", dest=os.path.dirname(_conda_wrapper(env_name)))
    p.copy(
        dest=_conda_wrapper(env_name),
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
    with actions(**kwds) as p:
        _create_wrapper_script(p, env_name)


def _conda_run_command(command: str, env_name: str, **kwargs: Any):
    """Run a single shell command in the context of a Conda environment.

    Wrapper around :py:func:`enoslib.api.run_command` that is conda aware.

    Args:
        command: The command to run
        env_name: An existing env_name in which the command will be run
    """
    # should run as root
    _inject_wrapper_script(env_name, **kwargs)
    extra_vars = kwargs.pop("extra_vars", {})
    extra_vars.update(ansible_python_interpreter=_conda_wrapper(env_name))
    # we are now ready to run this
    return run(command, extra_vars=extra_vars, **kwargs)


class _conda_play_on(actions):
    """Run Ansible modules in the context of a Conda environment."""

    def __init__(self, env_name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.conda_env = env_name
        self.extra_vars.update(ansible_python_interpreter=_conda_wrapper(env_name))
        _inject_wrapper_script(env_name, **kwargs)


class _Conda(Service):
    def __init__(self, *, nodes: Iterable[Host]):
        """Manage Conda on your nodes.

        This installs miniconda on the nodes(the latest version). Optionally it
        can also prepare an environment.

        Args:
            nodes: The list of the nodes to install conda on.

        Examples:

            .. literalinclude:: examples/conda.py
                :language: python
                :linenos:

        """
        self.nodes = nodes
        self._roles = Roles(nodes=self.nodes)

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
            env_name: name of the environment to create(if env_file is absent).
            packages: list of packages to install in the environment named env_name.
        """
        if packages is None:
            packages = []
        with actions(roles=self._roles) as p:
            p.apt(name="wget", state="present")
            p.shell(
                f"which conda || ls {CONDA_PREFIX}/bin/conda || "
                f"(wget --quiet {INSTALLER_URL} -O ~/miniconda.sh && "
                f"/bin/bash ~/miniconda.sh -b -p {CONDA_PREFIX} && "
                "rm ~/miniconda.sh)"
            )

            # Install the env if any and leave
            # Don't reinstall if it already exists
            if env_file is not None:
                # look for the env_name
                _env_name = _get_env_name(env_file)
                p.copy(src=env_file, dest="environment.yml")
                _shell_in_conda(
                    p,
                    (
                        f"(conda env list | grep '^{_env_name}') || "
                        "conda env create -f environment.yml"
                    ),
                    executable="/bin/bash",
                )
                _create_wrapper_script(p, _env_name)
                return

            # Install packages if any
            if env_name is not None and len(packages) > 0:
                _shell_in_conda(
                    p,
                    f"conda create --yes --name={env_name} {' '.join(packages)}",
                    executable="/bin/bash",
                )
                _create_wrapper_script(p, env_name)
            if env_name is None and len(packages) > 0:
                _shell_in_conda(
                    p,
                    f"conda create --yes -n enoslib {' '.join(packages)}",
                    executable="/bin/bash",
                )
                _create_wrapper_script(p, "enoslib")  # <!> hardcode

    def destroy(self):
        """Not implemented."""
        pass

    def backup(self):
        """Not implemented."""
        pass


class _Dask(Service):
    def __init__(
        self,
        scheduler: Host,
        worker: Iterable[Host],
        worker_args: str = "",
        env_file: Optional[str] = None,
    ):
        """Initialize a Dask cluster on the nodes.

        This installs a dask cluster from scratch by installing the
        dependency from the conda env_file. As a consequence bootstraping the
        dask cluster is easy but not fast (conda might be slow to do his
        job). Also, everything run as root which might not be ideal. Instead,
        you can have a look to the Dask Service
        (:py:class:`enoslib.service.conda.conda.Dask`) that will be faster at
        bootstraping Dask and run as a regular user.

        Args:
            scheduler  : the scheduler host
            worker     : the workers Hosts
            worker_args: args to be passed when starting the worker (see
                         dask-worker --help)
            env_file   : conda environment with you specific
                         dependencies.
                         Dask must be present in this environment.
        """
        self.scheduler = scheduler
        self.worker = worker
        self.worker_args = worker_args
        self.env_file = env_file
        self.env_name = _get_env_name(env_file) if env_file is not None else "__dask__"
        self.conda = _Conda(nodes=chain(worker, [scheduler]))
        self.roles = Roles(scheduler=[self.scheduler], worker=self.worker)

    def deploy(self):
        # Handle the environment
        if self.env_file is None:
            # Simply dask
            self.conda.deploy(env_name="__dask__", packages=["dask"])
        else:
            self.conda.deploy(env_file=self.env_file)

        # Start Dask cluster
        with actions(roles=self.roles) as p:
            p.apt(name="tmux", state="present")

        with actions(pattern_hosts="scheduler", roles=self.roles) as p:
            _shell_in_conda(
                p,
                (
                    "(tmux ls | grep dask-scheduler) ||"
                    f"( conda activate {self.env_name} &&"
                    "tmux new-session -s dask-scheduler -d 'exec dask-scheduler' )"
                ),
                executable="/bin/bash",
                task_name="Starting the dask scheduler",
            )
        s = self.scheduler.address
        cmd = (
            "tmux new-session -s dask-worker"
            f"-d 'exec dask-worker tcp://{s}:8786 {self.worker_args}'"
        )
        with actions(pattern_hosts="worker", roles=self.roles) as p:
            _shell_in_conda(
                p,
                (
                    "(tmux ls | grep dask-worker) ||"
                    f"( conda activate {self.env_name} &&"
                    f"{cmd} )"
                ),
                executable="/bin/bash",
                task_name="Starting the dask worker",
            )

    def destroy(self):
        with actions(pattern_hosts="scheduler", roles=self.roles) as p:
            p.shell(
                "tmux kill-session -t dask-scheduler || true",
                executable="/bin/bash",
                task_name="Killing the dask scheduler",
            )
        with actions(pattern_hosts="worker", roles=self.roles) as p:
            p.shell(
                "tmux kill-session -t dask-worker || true",
                executable="/bin/bash",
                task_name="Killing the dask worker ",
            )


def in_conda_cmd(cmd: str, env: str, prefix: str):
    """Build a command line that will run inside a conda env.

    Make sure conda env is sourced correctly.

    Args:
        cmd: The command to run
        env: The conda environment to activate
        prefix: The conda prefix, where the conda installation is

    Return:
        The command string prefixed by the right command to jump into the
        conda env.
    """
    return f"source {prefix}/etc/profile.d/conda.sh && conda activate andromak && {cmd}"


def conda_from_env():
    """
    Infer the prefix and conda env name from the environment variable.

    The documentation is weak about conda environment variables. FWIU the
    CONDA_PREFIX will point to the location of the conda env. In this situation
    CONDA_PREFIX could be something like: /home/msimonin/miniconda3/envs/myenv
    so we want to return prefix=/home/msimonin/miniconda3/, env=myenv.

    In the case the default (base) env is used, CONDA_PREFIX will look like this
    /home/msimonin/miniconda3 because base related files are put at the to level
    We can check the CONDA_DEFAULT_ENV to check the name of the current env
    """
    import os
    from pathlib import Path

    conda_prefix = os.environ.get("CONDA_PREFIX")
    conda_env_name = os.environ.get("CONDA_DEFAULT_ENV")
    if not conda_prefix:
        raise ValueError("CONDA_PREFIX not set, are you running a conda environment ?")
    if not conda_env_name:
        raise ValueError(
            "CONDA_DEFAULT_ENV not set, are you running a conda environment ?"
        )

    prefix = Path(conda_prefix)
    if conda_env_name != "base":
        prefix = prefix.parent.parent

    # Check if prefix contains the etc/profile.d/conda.sh files
    if not (prefix / "etc" / "profile.d" / "conda.sh").exists():
        raise ValueError(
            f"Can't infer where are the profile scripts in the env {prefix}"
        )

    # all clear we got a correct prefix and env...
    # returning them so that you can feed them in the module functions
    return str(prefix), conda_env_name


class Dask(Service):
    def __init__(
        self,
        conda_env: str,
        conda_prefix: str = None,
        scheduler: Host = None,
        workers: Iterable[Host] = None,
        worker_args: str = "",
        run_as: str = "root",
    ):
        """Deploy a Dask Cluster.

        It bootstraps a Dask scheduler and workers by activating the passed
        conda environment.
        User must have an environment ready with, at least, dask installed
        inside. The agents will be started as the passed user.

        It can be used as a context manager.
        Note that the exit method isn't optimal though (see
        :py:method:`enoslib.service.conda.conda.AutoDask.destroy`)

        Args:
            conda_env   : name of the conda environment (on the remote system)
            conda_prefix: prefix of the conda installation (will be used to
                          bring conda in the env) Default to
                          /home/<run_as>/miniconda3
            scheduler   : Host that will serve as the dask scheduler
            workers     : List of Host that will serve as workers
            worker_args : specific worker args to pass (e.g "--nthreads 1
                          --nprocs 8")
            run_as      : remote user to use. Conda must be available to this
                          user.

        Examples:

            `Notebook <examples/dask.ipynb>`_
        """
        self.conda_env = conda_env
        if conda_prefix is None:
            self.conda_prefix = f"/home/{run_as}/miniconda3"
        else:
            self.conda_prefix = conda_prefix
        self.scheduler = scheduler
        self.workers = workers
        self.worker_args = worker_args
        self.run_as = run_as

        # computed
        self.roles = Roles(scheduler=[self.scheduler], worker=self.workers)
        # can be set to optimize destroy
        self.client = None

    def in_conda_cmd(self, cmd: str):
        """Transforms a command to be executed in the context of the current conda env.

        Args:
            cmd: the command string

        Returns:
            The transformed command string prefixed by some other to activate
            the conda env.
        """
        return in_conda_cmd(cmd, self.conda_env, self.conda_prefix)

    def deploy(self):
        cmd = self.in_conda_cmd("dask-scheduler")
        print(cmd)
        with actions(
            pattern_hosts="scheduler",
            roles=self.roles,
            run_as=self.run_as,
            gather_facts=False,
        ) as p:
            p.raw(
                "(tmux ls | grep dask-scheduler ) "
                " || "
                f"tmux new-session -s dask-scheduler -d '{cmd}'",
                executable="/bin/bash",
            )
            p.wait_for(host="{{ inventory_hostname }}", port="8786")

        scheduler_addr = self.roles["scheduler"][0].address
        cmd = self.in_conda_cmd(
            f"dask-worker tcp://{scheduler_addr}:8786 {self.worker_args}"
        )
        with actions(
            pattern_hosts="worker",
            roles=self.roles,
            run_as=self.run_as,
            gather_facts=False,
        ) as p:
            p.raw(
                (
                    "(tmux ls | grep dask-worker )"
                    " || "
                    f"tmux new-session -s dask-worker -d '{cmd}'"
                ),
                executable="/bin/bash",
            )

    def destroy(self):
        """Destroy the dask cluster.

        Note that client.shutdown() is much more efficient.
        """
        if self.client is not None:
            self.client.shutdown()
        else:
            # wipe all tmux created
            with actions(
                pattern_hosts="scheduler",
                roles=self.roles,
                gather_facts=False,
                run_as=self.run_as,
            ) as p:
                p.raw(
                    "tmux kill-session -t dask-scheduler || true",
                    executable="/bin/bash",
                    task_name="Killing the dask scheduler",
                )
            with actions(
                pattern_hosts="worker",
                roles=self.roles,
                gather_facts=False,
                run_as=self.run_as,
            ) as p:
                p.raw(
                    "tmux kill-session -t dask-worker || true",
                    executable="/bin/bash",
                    task_name="Killing the dask worker ",
                )

    def __enter__(self):
        self.deploy()
        return self

    def __exit__(self, *args):
        self.destroy()
