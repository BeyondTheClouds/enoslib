from pathlib import Path
import os

from enoslib.api import play_on, __python3__, __default_python3__, __docker__
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
        self,
        *,
        collector=None,
        agent=None,
        ui=None,
        network=None,
        agent_conf=None,
        remote_working_dir="/builds/monitoring",
        priors=[__python3__, __default_python3__, __docker__],
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
            prior (): priors to apply


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
        self.remote_working_dir = remote_working_dir
        self.remote_telegraf_conf = os.path.join(
            self.remote_working_dir, "telegraf.conf"
        )
        self.remote_influxdata = os.path.join(self.remote_working_dir, "influxdb-data")
        self.priors = priors

    def deploy(self):
        """Deploy the monitoring stack"""
        if self.collector is None:
            return

        # Some requirements
        with play_on(pattern_hosts="all", roles=self._roles, priors=self.priors) as p:
            p.pip(display_name="Installing python-docker", name="docker")

        # Deploy the collector
        _path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

        with play_on(pattern_hosts="collector", roles=self._roles) as p:
            p.docker_container(
                display_name="Installing",
                name="influxdb",
                image="influxdb",
                detach=True,
                network_mode="host",
                state="started",
                volumes=[f"{self.remote_influxdata}:/var/lib/influxdb"],
            )
            p.wait_for(
                display_name="Waiting for InfluxDB to be ready",
                # I don't have better solution yet
                # The ci requirements are a bit annoying...
                host="172.17.0.1",
                port="8086",
                state="started",
                delay=2,
                timeout=120,
            )

        # Deploy the agents
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            collector_address = self.collector[0].extra[self.network + "_ip"]
        else:
            collector_address = self.collector[0].address

        extra_vars = {"collector_address": collector_address}
        with play_on(
            pattern_hosts="agent", roles=self._roles, extra_vars=extra_vars
        ) as p:
            p.file(path=self.remote_working_dir, state="directory")
            p.template(
                display_name="Generating the configuration file",
                src=os.path.join(_path, self.agent_conf),
                dest=self.remote_telegraf_conf,
            )

            volumes = [
                f"{self.remote_telegraf_conf}:/etc/telegraf/telegraf.conf",
                "/sys:/rootfs/sys:ro",
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
        ui_address = None
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            ui_address = self.ui[0].extra[self.network + "_ip"]
        else:
            # NOTE(msimonin): ping on docker bridge address for ci testing
            ui_address = "172.17.0.1"

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
                # NOTE(msimonin): ping on docker bridge address for ci testing
                host=ui_address,
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
            p.file(path=f"{self.remote_influxdata}", state="absent")

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
            backup_path = os.path.join(self.remote_working_dir, "influxdb-data.tar.gz")
            p.docker_container(
                display_name="Stopping InfluxDB", name="influxdb", state="stopped"
            )
            p.archive(
                display_name="Archiving the data volume",
                path=f"{self.remote_influxdata}",
                dest=backup_path,
            )

            p.fetch(
                display_name="Fetching the data volume",
                src=backup_path,
                dest=str(Path(_backup_dir, "influxdb-data.tar.gz")),
                flat=True,
            )

            p.docker_container(
                display_name="Restarting InfluxDB",
                name="influxdb",
                state="started",
                force_kill=True,
            )
