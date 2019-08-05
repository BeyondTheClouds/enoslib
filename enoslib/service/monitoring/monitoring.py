from pathlib import Path
import os

from enoslib.api import play_on
from ..service import Service


def _to_abs(path):
    """Make sure the path is absolute."""
    _path = Path(path)
    if not _path.is_absolute():
        # prepend the cwd
        _path = Path(Path.cwd(), _path)
    return _path


class Monitoring(Service):
    def __init__(
        self, *, collector=None, agent=None, ui=None, network=None, agent_conf=None
    ):
        """Deploy a TIG stack: Telegraf, InfluxDB, Grafana.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a monitoring stack on your nodes. It's opinionated
        out of the box but allow for some convenient customizations.


        Args:
            collector (list): list of :py:class:`enoslib.Host` where the
                              collector will be installed
            agent (list): list of :py:class:`enoslib.Host` where the agent will
                          be installed
            ui (list): list of :py:class:`enoslib.Host` where the UI will
                       be installed
            network (str): network role to use for the monitoring traffic.
                           Agents will us this network to send their metrics to
                           the collector. If none is given, the agent will us
                           the address attribute of :py:class:`enoslib.Host` of
                           the collector (the first on currently)
            agent_conf (str): path to an alternative configuration file


        Examples:

            .. literalinclude:: examples/monitoring.py
                :language: python
                :linenos:


        """
        self.collector = collector if collector else []
        self.agent = agent if agent else []
        self.ui = ui if agent else []
        self.network = network
        self._roles = {}
        self._roles.update(collector=self.collector, agent=self.agent, ui=self.ui)
        if agent_conf is None:
            self.agent_conf = "telegraf.conf.j2"
        else:
            self.agent_conf = _to_abs(agent_conf)

    def deploy(self):
        """Deploy the monitoring stack"""
        if self.collector is None:
            return

        # Some requirements
        with play_on(pattern_hosts="all", roles=self._roles) as p:
            p.apt(
                display_name="Installing python-setuptools",
                name="python-pip",
                state="present",
                update_cache=True,
            )
            p.pip(display_name="Installing python-docker", name="docker")
            p.shell(
                "which docker || (curl -sSL https://get.docker.com/ | sh)",
                display_name="Installing docker",
            )

        # Deploy the collector
        with play_on(pattern_hosts="collector", roles=self._roles) as p:

            p.docker_container(
                display_name="Installing",
                name="influxdb",
                image="influxdb",
                detach=True,
                network_mode="host",
                state="started",
                volumes=["/influxdb-data:/var/lib/influxdb"],
            )
            p.wait_for(
                display_name="Waiting for InfluxDB to be ready",
                host="localhost",
                port="8086",
                state="started",
                delay=2,
                timeout=120,
            )

        # Deploy the agents
        _path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            collector_address = self.collector[0].extra[self.network + "_ip"]
        else:
            collector_address = self.collector[0].address
        extra_vars = {"collector_address": collector_address}
        with play_on(
            pattern_hosts="agent", roles=self._roles, extra_vars=extra_vars
        ) as p:
            p.template(
                display_name="Generating the configuration file",
                src=os.path.join(_path, self.agent_conf),
                dest="/telegraf.conf",
            )

            volumes = [
                "/telegraf.conf:/etc/telegraf/telegraf.conf",
                "sys:/rootfs/sys:ro",
                "/proc:/rootfs/proc:ro",
                "/var/run/docker.sock:/var/run/docker.sock:ro",
            ]

            p.docker_container(
                display_name="Installing Telegraf",
                name="telegraf",
                image="telegraf",
                detach=True,
                state="started",
                network_mode="host",
                volumes=volumes,
                env={"HOST_PROC": "/rootfs/proc", "HOST_SYS": "/rootfs/sys"},
            )
        # Deploy the UI
        with play_on(pattern_hosts="ui", roles=self._roles) as p:
            p.docker_container(
                display_name="Installing Grafana",
                name="grafana",
                image="grafana/grafana",
                detach=True,
                network_mode="host",
                state="started",
            )
            p.wait_for(
                display_name="Waiting for grafana to be ready",
                host="localhost",
                port=3000,
                state="started",
                delay=2,
                timeout=120,
            )

    def destroy(self):
        """Destroy the monitoring stack.

        This destroys all the container and associated volumes.
        """
        with play_on(pattern_hosts="ui", roles=self._roles) as p:
            p.docker_container(
                display_name="Destroying Grafana",
                name="grafana",
                state="absent",
                force_kill=True,
            )

        with play_on(pattern_hosts="agent", roles=self._roles) as p:
            p.docker_container(
                display_name="Destroying telegraf", name="telegraf", state="absent"
            )

        with play_on(pattern_hosts="collector", roles=self._roles) as p:
            p.docker_container(
                display_name="Destroying InfluxDB",
                name="influxdb",
                state="absent",
                force_kill=True,
            )
            p.docker_volume(
                display_name="Destroying associated volumes",
                name="influxdb-data",
                state="absent",
            )

    def backup(self, backup_dir=None):
        """Backup the monitoring stack.

        Args:
            backup_dir (str): path of the backup directory to use.
        """

        def _check_path(backup_dir):
            """Make sur the backup_dir is created somewhere."""
            backup_path = _to_abs(backup_dir)
            # make sure it exists
            backup_path.mkdir(parents=True, exist_ok=True)
            return backup_path

        if backup_dir is None:
            backup_dir = Path.cwd()

        _backup_dir = _check_path(backup_dir)

        with play_on(pattern_hosts="collector", roles=self._roles) as p:
            p.docker_container(
                display_name="Stopping InfluxDB", name="influxdb", state="stopped"
            )
            p.archive(
                display_name="Archiving the data volume",
                path="/influxdb-data",
                dest="/influxdb-data.tar.gz",
            )

            p.fetch(
                display_name="Fetching the data volume",
                src="/influxdb-data.tar.gz",
                dest=str(Path(_backup_dir, "influxdb-data.tar.gz")),
                flat=True,
            )
            p.shell("docker start influxdb", display_name="Restarting InfluxDB")
