from pathlib import Path
import os
import time
from typing import Dict, List, Optional

from enoslib.api import __python3__, actions
from enoslib.objects import Host, Network, Roles
from enoslib.utils import get_address

from ..service import Service
from ..utils import _set_dir

CURRENT_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
LOCAL_OUTPUT_DIR = Path("__enoslib_locust__")


class Locust(Service):

    def __init__(
        self,
        master: Optional[Host] = None,
        agents: Optional[List[Host]] = None,
        networks: Optional[List[Network]] = None,
        remote_working_dir: str = "/builds/locust",
        backup_dir: Optional[Path] = None,
        priors: List[actions] = [__python3__],
        extra_vars: Dict = None,
    ):
        """Deploy a distributed Locust (see locust.io)

        This aims at deploying a distributed locust for load testing. Locust
        can be deployed either with its web interface or headless.

        Please note that this module assume that `discover_network` has been run before

        Args:
            master: :py:class:`~enoslib.objects.Host` where the
                    master will be installed
            agents: list of :py:class:`~enoslib.objects.Host` where the workers will
                    be installed
            networks: network role on which master, agents and targeted hosts
                     are deployed
            remote_working_dir: path to a remote location that will be used as working
                                directory
            backup_dir: local directory where the backup will be performed

        Examples:

            .. literalinclude:: examples/locust.py
                :language: python
                :linenos:
        """
        self.master = master
        assert self.master is not None

        self.agents = agents if agents is not None else []
        # create a separated working dir for each instance of the service
        self.remote_working_dir = os.path.join(remote_working_dir,
                                               str(int(time.time())))
        self.priors = priors
        self.roles = Roles()
        self.roles.update(master=[self.master], agent=self.agents)

        self.master_ip = get_address(self.master, networks=networks)

        # handle backup_dir
        self.backup_dir = _set_dir(backup_dir, LOCAL_OUTPUT_DIR)

        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

    def _repr_html_(self):
        from enoslib.html import html_from_dict
        return html_from_dict(str(self.__class__),
                              dict(master_ip=self.master_ip,
                                   backup_dir=self.backup_dir,
                                   remote_working_dir=self.remote_working_dir)
                              )

    def deploy(self):
        """Install Locust on master and agent hosts"""
        with actions(
            pattern_hosts="all",
            roles=self.roles,
            priors=self.priors,
            extra_vars=self.extra_vars,
        ) as p:
            p.pip(display_name="Installing Locust", name="locust")
            p.file(path=self.remote_working_dir, recurse="yes", state="directory")

    def destroy(self):
        """Stop locust."""
        with actions(
            pattern_hosts="all", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.shell("if pgrep locust; then pkill locust; fi")

    def backup(self, backup_dir: Optional[Path] = None):
        """Backup the locust files.

        We backup the remote working dir of the master.
        """
        _backup_dir = _set_dir(backup_dir, self.backup_dir)
        local_archive = f"{int(time.time())}.tar.gz"
        with actions(roles=self.master) as a:
            a.archive(path=self.remote_working_dir, dest=f"/tmp/{local_archive}")
            a.fetch(src=f"/tmp/{local_archive}", dest=str(_backup_dir))

    def run_with_ui(
        self,
        expe_dir: str,
        locustfile: str = "locustfile.py",
        density: int = 1,
        environment: Optional[Dict] = None,
    ):
        """Run locust with its web user interface.

        Args:
            expe_dir: path (relative or absolute) to the experiment directory
            file_name: path (relative or absolute) to the main locustfile
            density: number of locust workers to run per agent node
            environment: environment to pass to the execution
        """

        if environment is None:
            environment = {}
        locustpath = self.__copy_experiment(expe_dir, locustfile)
        with actions(
            pattern_hosts="master", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.shell(
                (
                    "nohup locust "
                    f"-f {locustpath} "
                    "--master "
                    f"--host={self.master_ip} "
                    "--csv enoslib "
                    f"--logfile={self.remote_working_dir}/locust-master.log &"
                ),
                environment=environment,
                display_name="Running locust (%s) on master..." % (locustpath),
            )

        with actions(
            pattern_hosts="agent", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            for i in range(density):
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--worker "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/locust-worker-{i}.log &"
                    ),
                    environment=environment,
                    chdir=self.remote_working_dir,
                    display_name=(
                        f"Running({locustpath}) on agents"
                        f"(master at {self.master_ip})..."
                    ),
                )

    def run_headless(
        self,
        expe_dir: str,
        locustfile: str = "locustfile.py",
        users: int = 1,
        spawn_rate: int = 1,
        run_time: int = 60,
        density: int = 1,
        environment: Optional[Dict] = None,
        blocking: bool = True
    ):
        """Run locust headless
        (see https://docs.locust.io/en/stable/running-locust-without-web-ui.html)

        Args:
            expe_dir: path (relative or absolute) to the experiment directory
            locustfile: path (relative or absolute) to the main locustfile
            nb_clients: total number of clients to spawn
            hatch_rate: number of clients to spawn per second
            run_time: time (in second) of the experiment
            density: number of locust worker to run per agent node
            environment: environment to pass to the execution
            blocking: whether the function block for the duration of the benchmark
        """

        if environment is None:
            environment = {}
        locustpath = self.__copy_experiment(expe_dir, locustfile)
        workers = len(self.roles["agent"]) * density
        with actions(
            pattern_hosts="master", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            cmd = (
                "nohup locust "
                f"-f {locustpath} "
                "--master "
                "--logfile=/tmp/locust.log "
                "--headless "
                f"--expect-workers {workers} "
                f"--users {users} "
                f"--spawn-rate {spawn_rate} "
                f"--run-time {str(run_time)}s "
                "--csv enoslib "
                f"--logfile={self.remote_working_dir}/locust-master.log &"
            )
            p.shell(cmd,
                environment=environment,
                chdir=self.remote_working_dir,
                display_name="Running locust (%s) on master..." % (locustfile),
            )
            # record the exact master command
            p.copy(dest=f"{self.remote_working_dir}/cmd", content=cmd)

        with actions(
            pattern_hosts="agent", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            for i in range(density):
                worker_local_id = f"locust-worker-{i}"
                environment.update(LOCUST_WORKER_LOCAL_ID=worker_local_id)
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--worker "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/{worker_local_id}.log &"
                    ),
                    environment=environment,
                    display_name=(
                        f"Running locust ({locustpath})"
                        f"on agents (master at {self.master_ip})..."
                    ),
                )
        if blocking:
            time.sleep(1.5 * int(run_time))

    def __copy_experiment(self, expe_dir: str, locustfile: str):
        src_dir = os.path.abspath(expe_dir)
        remote_dir = os.path.join(self.remote_working_dir, expe_dir)
        with actions(
            pattern_hosts="all", roles=self.roles, extra_vars=self.extra_vars
        ) as p:
            p.copy(
                src=src_dir,
                dest=self.remote_working_dir,
                mode="u=rw,g=r,o=r",
                display_name="Copying the experiment directory into each hosts",
            )
            if os.path.exists(os.path.join(src_dir, "requirements.txt")):
                p.pip(
                    requirements=os.path.join(remote_dir, "requirements.txt"),
                    display_name="Installing python deps",
                )
        locustpath = os.path.join(self.remote_working_dir, expe_dir, locustfile)
        return locustpath
