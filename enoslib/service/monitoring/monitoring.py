import json
from pathlib import Path
import os
from typing import Dict, List, Optional

from enoslib.api import play_on, __python3__, __default_python3__, __docker__
from enoslib.types import Host, Roles
from ..service import Service
from ..utils import _check_path, _to_abs


DEFAULT_UI_ENV = {"GF_SERVER_HTTP_PORT": "3000"}

DEFAULT_COLLECTOR_ENV = {"INFLUXDB_HTTP_BIND_ADDRESS": ":8086"}


class Monitoring(Service):
    def __init__(
        self,
        *,
        collector: List[Host] = None,
        agent: List[Host] = None,
        ui: List[Host] = None,
        network: List[Host] = None,
        agent_conf: Optional[str] = None,
        remote_working_dir: str = "/builds/monitoring",
        collector_env: Optional[Dict] = None,
        agent_env: Optional[Dict] = None,
        ui_env: Optional[Dict] = None,
        priors: List[play_on] = [__python3__, __default_python3__, __docker__],
    ):
        """Deploy a TIG stack: Telegraf, InfluxDB, Grafana.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a monitoring stack on your nodes. It's opinionated
        out of the box but allow for some convenient customizations.


        Args:
            collector: list of :py:class:`enoslib.Host` where the
                              collector will be installed
            agent: list of :py:class:`enoslib.Host` where the agent will
                          be installed
            ui: list of :py:class:`enoslib.Host` where the UI will
                       be installed
            network: network role to use for the monitoring traffic.
                           Agents will us this network to send their metrics to
                           the collector. If none is given, the agent will us
                           the address attribute of :py:class:`enoslib.Host` of
                           the collector (the first on currently)
            agent_conf: path to an alternative configuration file
            collector_env: environment variables to pass in the collector
                                  process environment
            agent_env: environment variables to pass in the agent process
                              envionment
            ui_env: environment variables to pass in the ui process
                           environment
            prior: priors to apply


        Examples:

            .. literalinclude:: examples/monitoring.py
                :language: python
                :linenos:


        """
        # Some initialisation and make mypy happy
        self.collector = collector if collector else []
        assert self.collector is not None
        self.agent = agent if agent else []
        assert self.agent is not None
        self.ui = ui if agent else []
        assert self.ui is not None

        self.network = network
        self._roles: Roles = {}
        self._roles.update(collector=self.collector, agent=self.agent, ui=self.ui)
        if agent_conf is None:
            self.agent_conf = Path("telegraf.conf.j2")
        else:
            self.agent_conf = _to_abs(Path(agent_conf))

        self.remote_working_dir = remote_working_dir
        self.remote_telegraf_conf = os.path.join(
            self.remote_working_dir, "telegraf.conf"
        )
        self.remote_influxdata = os.path.join(self.remote_working_dir, "influxdb-data")

        self.collector_env = DEFAULT_COLLECTOR_ENV
        collector_env = {} if not collector_env else collector_env
        self.collector_env.update(collector_env)
        self.agent_env = {} if not agent_env else agent_env
        self.ui_env = DEFAULT_UI_ENV
        ui_env = {} if not ui_env else ui_env
        self.ui_env.update(ui_env)

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

        # Handle port customisation
        _, collector_port = self.collector_env["INFLUXDB_HTTP_BIND_ADDRESS"].split(":")
        with play_on(pattern_hosts="collector", roles=self._roles) as p:
            p.docker_container(
                display_name="Installing",
                name="influxdb",
                image="influxdb",
                detach=True,
                network_mode="host",
                state="started",
                recreate="yes",
                env=self.collector_env,
                volumes=[f"{self.remote_influxdata}:/var/lib/influxdb"],
            )
            p.wait_for(
                display_name="Waiting for InfluxDB to be ready",
                # I don't have better solution yet
                # The ci requirements are a bit annoying...
                host="172.17.0.1",
                port=collector_port,
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
            env = {"HOST_PROC": "/rootfs/proc", "HOST_SYS": "/rootfs/sys"}
            env.update(self.agent_env)
            p.docker_container(
                display_name="Installing Telegraf",
                name="telegraf",
                image="telegraf",
                detach=True,
                state="started",
                recreate="yes",
                network_mode="host",
                volumes=volumes,
                env=env,
            )

        # Deploy the UI
        ui_address = None
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            ui_address = self.ui[0].extra[self.network + "_ip"]
        else:
            # NOTE(msimonin): ping on docker bridge address for ci testing
            ui_address = "172.17.0.1"

        # Handle port customisation
        ui_port = self.ui_env["GF_SERVER_HTTP_PORT"]
        with play_on(pattern_hosts="ui", roles=self._roles) as p:
            p.docker_container(
                display_name="Installing Grafana",
                name="grafana",
                image="grafana/grafana",
                detach=True,
                network_mode="host",
                env=self.ui_env,
                recreate="yes",
                state="started",
            )
            p.wait_for(
                display_name="Waiting for grafana to be ready",
                # NOTE(msimonin): ping on docker bridge address for ci testing
                host=ui_address,
                port=ui_port,
                state="started",
                delay=2,
                timeout=120,
            )
            p.uri(
                display_name="Add InfluxDB in Grafana",
                url=f"http://{ui_address}:{ui_port}/api/datasources",
                user="admin",
                password="admin",
                force_basic_auth=True,
                body_format="json",
                method="POST",
                # 409 means: already added
                status_code=[200, 409],
                body=json.dumps(
                    {
                        "name": "telegraf",
                        "type": "influxdb",
                        "url": f"http://{collector_address}:{collector_port}",
                        "access": "proxy",
                        "database": "telegraf",
                        "isDefault": True,
                    }
                ),
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

    def backup(self, backup_dir: Optional[str] = None):
        """Backup the monitoring stack.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        if backup_dir is None:
            _backup_dir = Path.cwd()
        else:
            _backup_dir = Path(backup_dir)

        _backup_dir = _check_path(_backup_dir)

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
