import os

from enoslib.api import play_on
from ..service import Service

CURRENT_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class Locust(Service):
    def __init__(self, master={}, agents={}, network=None, **kwargs):
        """Deploy a distributed Locust (see locust.io)

        This aims at deploying a distributed locust for load testing. Locust
        can be deployed either with its web interface or headless.

        Please note that this module assume that `discover_network` has been run before

        Args:
            master (list): list of :py:class:`enoslib.Host` where the
                              master will be installed
            agents (list): list of :py:class:`enoslib.Host` where the slave will
                          be installed
            network (str): network role on which master, agents and targeted hosts
                            are deployed

        Examples:

            .. literalinclude:: examples/locust.py
                :language: python
                :linenos:
        """
        self.master = master
        self.agents = agents
        self.network = network
        self.roles = {}
        self.roles.update(master=self.master, agent=self.agents)

        self.master_ip = self.master[0].extra[self.network + "_ip"]

    def deploy(self):
        """Install Locust on master and agent hosts"""
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.apt(
                display_name="Installing python-setuptools",
                name="python-pip",
                state="present",
                update_cache=True,
            )
            p.pip(display_name="Installing Locust", name="locustio")

    def destroy(self):
        """
        Stop locust
        """
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.shell("pkill locust")

    def run_with_ui(self, expe_dir, file_name, port="8089"):
        """Run locust with its web user interface.

        Args:
            expe_dir (string): path (relative or absolute) to the experiment directory
            file_name (string): path (relative or absolute) to the main locustfile
            port (string): port for locust web interface
        """
        self.__copy_experiment(expe_dir, file_name)
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    "-f /tmp/%s "
                    "--master "
                    "--host=%s "
                    "-P %s "
                    "--logfile=/tmp/locust.log &"
                )
                % (file_name, self.master_ip, port),
                display_name="Running locust (%s) on master..." % (file_name),
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    "-f /tmp/%s "
                    "--slave "
                    "--master-host=%s "
                    "--host=%s "
                    "--logfile=/tmp/locust.log &"
                )
                % (file_name, self.master_ip, self.master_ip),
                display_name="Running locust (%s) on agents (master at %s)..."
                % (file_name, self.master_ip),
            )

    def run_headless(
        self, expe_dir, file_name, nb_clients, hatch_rate, time, targeted_hosts=None
    ):
        """Run locust headless
        (see https://docs.locust.io/en/stable/running-locust-without-web-ui.html)

        Args:
            expe_dir (string): path (relative or absolute) to the experiment directory
            file_name (string): path (relative or absolute) to the main locustfile
            nb_clients (int): total number of clients to spawn
            hatch_rate (int): number of clients to spawn per second
            time (string): time of the experiment
        """

        self.__copy_experiment(expe_dir, file_name)
        with play_on(pattern_hosts="master", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    "-f /tmp/%s "
                    "--master "
                    "--host=%s "
                    "--logfile=/tmp/locust.log "
                    "--no-web "
                    "-c %s "
                    "-r %s "
                    "--run-time %s &"
                )
                % (file_name, self.master_ip, nb_clients, hatch_rate, time),
                display_name="Running locust (%s) on master..." % (file_name),
            )

        with play_on(pattern_hosts="agent", roles=self.roles) as p:
            p.shell(
                (
                    "nohup locust "
                    "-f /tmp/%s "
                    "--slave "
                    "--master-host=%s "
                    "--host=%s "
                    "--logfile=/tmp/locust.log &"
                )
                % (file_name, self.master_ip, self.master_ip),
                display_name="Running locust (%s) on agents (master at %s)..."
                % (file_name, self.master_ip),
            )

    def __copy_experiment(self, expe_dir, file_name):
        src_dir = os.path.abspath(expe_dir)
        src_dir_name = os.path.basename(os.path.normpath(src_dir))

        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.copy(
                src=src_dir,
                dest="/tmp/",
                mode="u=rw,g=r,o=r",
                display_name="Copying the experiment directory into each hosts",
            )

            if os.path.exists("%s/requirements.txt" % (src_dir)):
                p.pip(
                    requirements="/tmp/%s/requirements.txt" % (src_dir_name),
                    display_name="Installing python deps",
                )
