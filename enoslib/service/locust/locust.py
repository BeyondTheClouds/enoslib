import os
from typing import Dict, List, Optional

from enoslib.api import play_on, __python3__, __default_python3__
from enoslib.types import Host
from ..service import Service

CURRENT_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class Locust(Service):
    def __init__(
        self,
        master: Optional[List[Host]] = None,
        agents: Optional[List[Host]] = None,
        network: Optional[str] = None,
        remote_working_dir: str = "/builds/locust",
        priors: List[play_on] = [__python3__, __default_python3__],
    ):
        """Deploy a distributed Locust (see locust.io)

        This aims at deploying a distributed locust for load testing. Locust
        can be deployed either with its web interface or headless.

        Please note that this module assume that `discover_network` has been run before

        Args:
            master: list of :py:class:`enoslib.Host` where the
                    master will be installed
            agents: list of :py:class:`enoslib.Host` where the slave will
                    be installed
            network: network role on which master, agents and targeted hosts
                     are deployed
            remote_working_dir: path to a remote location that will be used as working
                                directory

        Examples:

            .. literalinclude:: examples/locust.py
                :language: python
                :linenos:
        """
        self.master = master if master is not None else []
        self.agents = agents if agents is not None else []
        self.remote_working_dir = remote_working_dir
        self.priors = priors
        self.roles: Dict = {}
        self.roles.update(master=self.master, agent=self.agents)
        if network is not None:
            self.master_ip = self.master[0].extra[network + "_ip"]
        else:
            self.master_ip = self.master[0].address

    def deploy(self):
        """Install Locust on master and agent hosts"""
        with play_on(pattern_hosts="all", roles=self.roles, priors=self.priors) as p:
            p.pip(display_name="Installing Locust", name="locustio")
            p.file(path=self.remote_working_dir, recurse="yes", state="directory")

    def destroy(self):
        """Stop locust."""
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.shell("if pgrep locust; then pkill locust; fi")

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
            density: number of locust slave to run per agent node
            environment: environment to pass to the execution
        """

        if environment is None:
            environment = {}
        locustpath = self.__copy_experiment(expe_dir, locustfile)
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    f"-f {locustpath} "
                    "--master "
                    f"--host={self.master_ip} "
                    f"--logfile={self.remote_working_dir}/locust-master.log &"
                ),
                environment=environment,
                display_name="Running locust (%s) on master..." % (locustpath),
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            for i in range(density):
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--slave "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/locust-slave-{i}.log &"
                    ),
                    environment=environment,
                    display_name=(
                        f"Running({locustpath}) on agents"
                        f"(master at {self.master_ip})..."
                    ),
                )

    def run_headless(
        self,
        expe_dir: str,
        locustfile: str = "locustfile.py",
        nb_clients: int = 1,
        hatch_rate: int = 1,
        run_time: str = "60s",
        density: int = 1,
        environment: Optional[Dict] = None,
    ):
        """Run locust headless
        (see https://docs.locust.io/en/stable/running-locust-without-web-ui.html)

        Args:
            expe_dir: path (relative or absolute) to the experiment directory
            locustfile: path (relative or absolute) to the main locustfile
            nb_clients: total number of clients to spawn
            hatch_rate: number of clients to spawn per second
            run_time: time of the experiment. e.g 300s, 20m, 3h, 1h30m, etc.
            density: number of locust slave to run per agent node
            environment: environment to pass to the execution
        """

        if environment is None:
            environment = {}
        locustpath = self.__copy_experiment(expe_dir, locustfile)
        slaves = len(self.roles["agent"]) * density
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    f"-f {locustpath} "
                    "--master "
                    "--logfile=/tmp/locust.log "
                    "--no-web "
                    f"--expect-slaves {slaves} "
                    f"--client {nb_clients} "
                    f"--hatch-rate {hatch_rate} "
                    f"--run-time {run_time} "
                    f"--logfile={self.remote_working_dir}/locust-master.log &"
                ),
                environment=environment,
                display_name="Running locust (%s) on master..." % (locustfile),
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            for i in range(density):
                p.shell(
                    (
                        "nohup locust "
                        f"-f {locustpath} "
                        "--slave "
                        f"--master-host={self.master_ip} "
                        f"--logfile={self.remote_working_dir}/locust-slave-{i}.log &"
                    ),
                    environment=environment,
                    display_name=(
                        f"Running locust ({locustpath})"
                        f"on agents (master at {self.master_ip})..."
                    ),
                )

    def __copy_experiment(self, expe_dir: str, locustfile: str):
        src_dir = os.path.abspath(expe_dir)
        remote_dir = os.path.join(self.remote_working_dir, expe_dir)
        with play_on(pattern_hosts="all", roles=self.roles) as p:
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
