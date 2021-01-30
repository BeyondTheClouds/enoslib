from pathlib import Path
import os
from typing import Dict, List, Optional

from enoslib.api import play_on, run_ansible
from enoslib.types import Host, Roles
from ..service import Service
from ..utils import _check_path, _to_abs


DEFAULT_UI_ENV = {"GF_SERVER_HTTP_PORT": "3000"}

DEFAULT_COLLECTOR_ENV = {"INFLUXDB_HTTP_BIND_ADDRESS": ":8086"}

DEFAULT_AGENT_IMAGE = "telegraf"

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


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
        quick way to deploy a monitoring stack on your nodes. Except for
        telegraf agents which will use a binary file for armv7 (FIT/IoT-LAB).

        It's opinionated out of the box but allow for some convenient
        customizations.

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
        self.ui = ui if ui else []
        assert self.ui is not None

        self.network = network
        self._roles: Roles = {}
        self._roles.update(influxdb=self.collector, telegraf=self.agent, grafana=self.ui)
        self.remote_working_dir = remote_working_dir

        self.collector_env = DEFAULT_COLLECTOR_ENV
        collector_env = {} if not collector_env else collector_env
        self.collector_env.update(collector_env)

        # agent options
        self.agent_env = {} if not agent_env else agent_env
        if agent_conf is None:
            self.agent_conf = "telegraf.conf.j2"
        else:
            self.agent_conf = str(_to_abs(Path(agent_conf)))
        self.agent_image = agent_image

        # ui options
        self.ui_env = DEFAULT_UI_ENV
        ui_env = {} if not ui_env else ui_env
        self.ui_env.update(ui_env)

        self.priors = priors

        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

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
        if self.collector is None:
            return

        if self.priors:
            with play_on(
                pattern_hosts="all",
                roles=self._roles,
                priors=self.priors,
                extra_vars=self.extra_vars
            ):
                # keep an empty block to run priors given by user
                pass

        _, collector_port = self.collector_env["INFLUXDB_HTTP_BIND_ADDRESS"].split(":")
        ui_address = None
        if self.network is not None:
            # This assumes that `discover_network` has been run before
            ui_address = self.ui[0].extra[self.network + "_ip"]
        else:
            # NOTE(msimonin): ping on docker bridge address for ci testing
            ui_address = "172.17.0.1"

        extra_vars = {
            "enos_action": "deploy",
            "collector_address": self._get_collector_address(),
            "collector_port": collector_port,
            "collector_env": self.collector_env,
            "collector_type": "influxdb",
            "agent_conf": self.agent_conf,
            "agent_image": self.agent_image,
            "remote_working_dir": self.remote_working_dir,
            "ui_address": ui_address,
            "ui_port": self.ui_env["GF_SERVER_HTTP_PORT"],
            "ui_env": self.ui_env
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook], roles=self._roles, extra_vars=extra_vars
        )

    def destroy(self):
        """Destroy the monitoring stack.

        This destroys all the container and associated volumes.
        """
        extra_vars = {
            "enos_action": "destroy",
            "remote_working_dir": self.remote_working_dir,
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")

        run_ansible(
            [_playbook],
            roles=self._roles,
            extra_vars=extra_vars
        )

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

        extra_vars = {
            "enos_action": "backup",
            "remote_working_dir": self.remote_working_dir,
            "backup_dir": str(_backup_dir)
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")

        run_ansible(
            [_playbook],
            roles={"influxdb": self._roles["influxdb"]},
            extra_vars=extra_vars
        )


class MonitoringIPv6(Service):
    def __init__(
        self,
        collector: Host,
        agent: List[Host],
        *,
        ui: Host = None,
        remote_working_dir: str = "/builds/monitoring",
        agent_env: Optional[Dict] = None,
    ):
        """Deploy a TPG stack: Telegraf, Prometheus, Grafana.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a monitoring stack on your nodes. Except for
        telegraf agents which will use a binary file for armv7 (FIT/IoT-LAB).

        It's opinionated out of the box but allow for some convenient
        customizations.

        Args:
            collector: :py:class:`enoslib.Host` where the
                              collector will be installed
            ui: :py:class:`enoslib.Host` where the UI will
                       be installed
            agent: list of :py:class:`enoslib.Host` where the agent will
                          be installed
        """

        # Some initialisation and make mypy happy
        self.collector = [collector]
        assert self.collector is not None
        self.agent = agent
        assert self.agent is not None
        self.ui = [ui] if ui else []
        assert self.ui is not None

        self._roles: Roles = {}
        self._roles.update(
            prometheus=self.collector, telegraf=self.agent, grafana=self.ui
        )
        self.remote_working_dir = remote_working_dir
        self.prometheus_port = 9090

        # We force python3
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}

    def deploy(self):
        """Deploy the monitoring stack"""
        if self.collector is None:
            return

        extra_vars = {
            "enos_action": "deploy",
            "collector_type": "prometheus",
            "remote_working_dir": self.remote_working_dir,
            "collector_port": self.prometheus_port,
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")
        run_ansible(
            [_playbook], roles=self._roles, extra_vars=extra_vars
        )

    def destroy(self):
        """Destroy the monitoring stack.

        This destroys all the container and associated volumes.
        """
        extra_vars = {
            "enos_action": "destroy",
            "remote_working_dir": self.remote_working_dir,
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")

        run_ansible(
            [_playbook],
            roles=self._roles,
            extra_vars=extra_vars
        )

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

        extra_vars = {
            "enos_action": "backup",
            "remote_working_dir": self.remote_working_dir,
            "collector_port": self.prometheus_port,
            "backup_dir": str(_backup_dir)
        }
        extra_vars.update(self.extra_vars)
        _playbook = os.path.join(SERVICE_PATH, "monitoring.yml")

        run_ansible(
            [_playbook],
            roles={"prometheus": self._roles["prometheus"]},
            extra_vars=extra_vars
        )
