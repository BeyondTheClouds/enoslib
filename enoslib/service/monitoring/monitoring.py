from pathlib import Path
import os
from typing import Dict, List, Optional

from enoslib.api import play_on, run_ansible, run_play
from enoslib.types import Host
from ..service import Service
from ..utils import _check_path, _to_abs


DEFAULT_UI_ENV = {"GF_SERVER_HTTP_PORT": "3000"}

DEFAULT_COLLECTOR_ENV = {"INFLUXDB_HTTP_BIND_ADDRESS": ":8086"}

DEFAULT_AGENT_IMAGE = "telegraf"

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class InfluxDB(Service):
    def __init__(
        self,
        hosts: List[Host],
        collector_address: str,
        *,
        remote_working_dir: str = "/builds/monitoring",
        collector_env: Optional[Dict] = None,
        extra_vars: Dict = None,
    ):
        self.hosts = hosts
        self.collector_env = DEFAULT_COLLECTOR_ENV
        collector_env = {} if not collector_env else collector_env
        self.collector_env.update(collector_env)
        self.collector_address = collector_address
        self.remote_working_dir = remote_working_dir
        self.extra_vars = extra_vars

    def deploy(self):
        """Deploy the monitoring stack"""
        _, collector_port = self.collector_env["INFLUXDB_HTTP_BIND_ADDRESS"].split(":")

        extra_vars = {
            "enos_action": "deploy",
            "collector_address": self.collector_address,
            "collector_port": collector_port,
            "collector_env": self.collector_env,
            "remote_working_dir": self.remote_working_dir,
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook],
            roles={"influxdb": self.hosts},
            extra_vars=extra_vars
        )

    def destroy(self):
        """Destroy InfluxDB.

        This destroys InfluxDB container and associated volumes.
        """
        extra_vars = {
            "enos_action": "destroy",
            "remote_working_dir": self.remote_working_dir,
        }
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        extra_vars.update(self.extra_vars)
        run_ansible(
            [_playbook],
            roles={"influxdb": self.hosts},
            extra_vars=extra_vars
        )

    def backup(self, backup_dir: Optional[str] = None):
        """Backup InfluxDB.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        if backup_dir is None:
            _backup_dir = Path.cwd()
        else:
            _backup_dir = Path(backup_dir)

        _backup_dir = _check_path(_backup_dir)

        extra_vars = {
            "enos_action": "backup",
            "remote_working_dir": self.remote_working_dir,
            "backup_dir": str(_backup_dir)
        }
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        extra_vars.update(self.extra_vars)
        run_ansible(
            [_playbook],
            roles={"influxdb": self.hosts},
            extra_vars=extra_vars
        )


class Telegraf(Service):
    def __init__(
        self,
        hosts: List[Host],
        *,
        remote_working_dir: str = "/builds/monitoring",
        agent_conf: Optional[str] = None,
        agent_env: Optional[Dict] = None,
        agent_image: str = DEFAULT_AGENT_IMAGE,
        collector_address: Optional[str] = None,
        collector_port: Optional[int] = None,
        agent_listen_address: Optional[str] = None,
        extra_vars: Dict = None,
    ):
        self.hosts = hosts
        self.remote_working_dir = remote_working_dir
        # agent options
        self.agent_env = {} if not agent_env else agent_env
        if agent_conf is None:
            self.agent_conf = "telegraf.conf.j2"
        else:
            self.agent_conf = str(_to_abs(Path(agent_conf)))
        self.agent_image = agent_image
        self.collector_address = collector_address
        self.collector_port = collector_port
        self.agent_listen_address = agent_listen_address
        self.extra_vars = extra_vars

    def deploy(self):
        extra_vars = {
            "enos_action": "deploy",
            "agent_conf": self.agent_conf,
            "agent_image": self.agent_image,
            "remote_working_dir": self.remote_working_dir,
        }
        if (self.collector_address is not None and self.collector_port is not None):
            extra_vars.update(
                {
                    "collector_address": self.collector_address,
                    "collector_port": self.collector_port,
                }
            )
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook],
            roles={"telegraf": self.hosts},
            extra_vars=extra_vars
        )

    def destroy(self):
        """Destroy Telegraf agent.

        This destroys Telegraf container
        """
        extra_vars = {
            "enos_action": "destroy",
            "remote_working_dir": self.remote_working_dir,
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook],
            roles={"telegraf": self.hosts},
            extra_vars=extra_vars
        )


class Grafana(Service):
    def __init__(
        self,
        hosts: List[Host],
        ui_address: str,
        collector_address: str,
        collector_port: int,
        *,
        ui_env: Optional[Dict] = None,
        extra_vars: Dict = None,
    ):
        self.hosts = hosts
        self.ui_address = ui_address
        self.collector_address = collector_address
        self.collector_port = collector_port

        self.ui_env = DEFAULT_UI_ENV
        ui_env = {} if not ui_env else ui_env
        self.ui_env.update(ui_env)
        self.extra_vars = extra_vars

    def deploy(self):
        extra_vars = {
            "enos_action": "deploy",
            "collector_address": self.collector_address,
            "collector_port": self.collector_port,
            "ui_address": self.ui_address,
            "ui_port": self.ui_env["GF_SERVER_HTTP_PORT"],
            "ui_env": self.ui_env
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook],
            roles={"grafana": self.hosts},
            extra_vars=extra_vars
        )

    def destroy(self):
        """Destroy Grafana service

        This destroys Grafana container
        """
        extra_vars = {
            "enos_action": "destroy",
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook],
            roles={"grafana": self.hosts},
            extra_vars=extra_vars
        )


class Monitoring(Service):
    def __init__(
        self,
        *,
        collector: List[Host] = None,
        agent: List[Host] = None,
        ui: List[Host] = None,
        network: str = None,
        remote_working_dir: str = "/builds/monitoring",
        collector_env: Optional[Dict] = None,
        agent_conf: Optional[str] = None,
        agent_env: Optional[Dict] = None,
        agent_image: str = DEFAULT_AGENT_IMAGE,
        ui_env: Optional[Dict] = None,
        priors: List[play_on] = [],
        extra_vars: Dict = None,
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
            collector_env: environment variables to pass in the collector
                                  process environment
            agent_conf: path to an alternative configuration file
            agent_env: environment variables to pass in the agent process
                              envionment
            agent_image: docker image to use for the agent (telegraf)
            ui_env: environment variables to pass in the ui process
                           environment
            prior: priors to apply
            extra_vars: extra variables to pass to Ansible


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

        self.priors = priors
        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

        collector_env = DEFAULT_COLLECTOR_ENV if not collector_env else collector_env
        _, collector_port = collector_env["INFLUXDB_HTTP_BIND_ADDRESS"].split(":")
        self.grafana = Grafana(
            hosts=self.ui,
            ui_address=self._get_ui_address(),
            collector_address=self._get_collector_address(),
            collector_port=collector_port,
            extra_vars=self.extra_vars
        )
        self.telegraf = Telegraf(
            hosts=self.agent,
            remote_working_dir=remote_working_dir,
            agent_conf=agent_conf,
            agent_env=agent_env,
            agent_image=agent_image,
            collector_address=self._get_collector_address(),
            collector_port=collector_port,
            extra_vars=self.extra_vars,
        )
        self.influxdb = InfluxDB(
            hosts=self.collector,
            collector_address=self._get_collector_address(),
            remote_working_dir=remote_working_dir,
            collector_env=collector_env,
            extra_vars=self.extra_vars,
        )

    def _get_ui_address(self) -> str:
        """
        Auxiliary method to get UI's IP address

        Returns:
            str with IP address
        """
        ui_address = None
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            ui_address = self.ui[0].extra[self.network + "_ip"]
        else:
            # NOTE(msimonin): ping on docker bridge address for ci testing
            ui_address = "172.17.0.1"
        return ui_address

    def _get_collector_address(self) -> str:
        """
        Auxiliary method to get collector's IP address

        Returns:
            str with IP address
        """
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            return self.collector[0].extra[self.network + "_ip"]
        else:
            return self.collector[0].address

    def deploy(self):
        """Deploy the monitoring stack"""
        with play_on(
            pattern_hosts="all",
            roles={
                "influxdb": self.collector,
                "telegraf": self.agent,
                "grafana": self.ui,
            },
            priors=self.priors,
            extra_vars=self.extra_vars,
        ):
            # keep an empty block to run priors given by user
            pass

        self.influxdb.deploy()
        self.telegraf.deploy()
        self.grafana.deploy()

    def destroy(self):
        """Destroy the monitoring stack.

        This destroys all the container and associated volumes.
        """
        self.grafana.destroy()
        self.telegraf.destroy()
        self.influxdb.destroy()

    def backup(self, backup_dir: Optional[str] = None):
        """Backup the monitoring stack.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        self.influxdb.backup(backup_dir)
