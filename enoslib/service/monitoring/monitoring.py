from pathlib import Path
import os
from typing import Dict, List, Optional, Union, Tuple
from enum import Enum
from ipaddress import IPv4Interface, IPv6Interface

from enoslib.api import run_ansible
from enoslib.types import Host, Roles
from ..service import Service
from ..utils import _check_path, _to_abs


DEFAULT_UI_ENV = {"GF_SERVER_HTTP_PORT": "3000"}

DEFAULT_COLLECTOR_ENV = {"INFLUXDB_HTTP_BIND_ADDRESS": ":8086"}

DEFAULT_AGENT_IMAGE = "telegraf"

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class IPVersion(Enum):
    IPV4 = 1
    IPV6 = 2


def _get_address(host: Host, network: Union[str, Tuple[str, IPVersion]]) -> str:
    """Auxiliary function to get the IP address for the Host

    Gets IP address from Host class, depending on network parameter:
    - None: gets from host.address
    - (role, ipv4): search in host.extra_addresses for an IPv4 with (role, ipv4)
    - (role, version): search in host.extra_address for an IP with (role, version)

    Args:
        host: Host information
        network: Network information
    Returns:
        str: IP address from host
    """
    if network is None:
        return host.address
    if isinstance(network, Tuple):
        role = network[0]
        version = network[1]
    else:
        role = network
        version = IPVersion.IPV4

    version_type = {
        IPVersion.IPV4: IPv4Interface,
        IPVersion.IPV6: IPv6Interface,
    }

    for ip_addr in host.extra_addresses:
        if (role in ip_addr.roles and isinstance(
            ip_addr.ip, version_type[version])):
            return str(ip_addr.ip.ip)

    raise ValueError(
        f"IP address not found. Host: {host}, Role: {role}, Version: {version}"
    )


class TIGMonitoring(Service):
    def __init__(
        self,
        collector: Host,
        agent: List[Host],
        *,
        ui: Host = None,
        network: Union[str, Tuple[str, IPVersion]] = None,
        remote_working_dir: str = "/builds/monitoring",
        collector_env: Optional[Dict] = None,
        agent_conf: Optional[str] = None,
        agent_env: Optional[Dict] = None,
        agent_image: str = DEFAULT_AGENT_IMAGE,
        ui_env: Optional[Dict] = None,
        extra_vars: Dict = None,
    ):
        """Deploy a TIG stack: Telegraf, InfluxDB, Grafana.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a monitoring stack on your nodes. Except for
        telegraf agents which will use a binary file for armv7 (FIT/IoT-LAB).

        It's opinionated out of the box but allow for some convenient
        customizations.

        Args:
            collector: :py:class:`enoslib.Host` where the
                              collector will be installed
            agent: list of :py:class:`enoslib.Host` where the agent will
                          be installed
            ui: :py:class:`enoslib.Host` where the UI will
                       be installed
            network: network to use for the monitoring traffic.
                        Agents will send their metrics to the collector using
                        this IP address. In the same way, the ui will use this IP to
                        connect to collector.
                        The IP address is taken from :py:class:`enoslib.Host`, depending
                        on this parameter:
                        - None: IP address = host.address
                        - str: Network role. Get the first IPv4 address available in
                        host.extra_addresses with this network role.
                        - Tuple(str, IPVersion). Network role and protocol version.
                        Get the first IPVersion (ipv4 or ipv6) address in
                        host.extra_ddresses with this network role and version.
                        Note that this parameter depends on calling sync_network_info to
                        fill the extra_addresses structure.
                        Raises an exception if no IP address is found
            remote_working_dir: path to a remote location that
                    will be used as working directory
            collector_env: environment variables to pass in the collector
                                  process environment
            agent_conf: path to an alternative configuration file
            agent_env: environment variables to pass in the agent process
                              envionment
            agent_image: docker image to use for the agent (telegraf)
            ui_env: environment variables to pass in the ui process
                           environment
            extra_vars: extra variables to pass to Ansible


        Examples:

            .. literalinclude:: examples/monitoring.py
                :language: python
                :linenos:
        """
        # Some initialisation and make mypy happy
        self.collector = collector
        assert self.collector is not None
        self.agent = agent
        assert self.agent is not None
        self.ui = ui
        assert self.ui is not None

        self.network = network
        self._roles: Roles = {}
        self._roles.update(
            influxdb=[self.collector], telegraf=self.agent, grafana=[self.ui]
        )
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

        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

    def deploy(self):
        """Deploy the monitoring stack"""
        _, collector_port = self.collector_env["INFLUXDB_HTTP_BIND_ADDRESS"].split(":")
        ui_address = _get_address(self.ui, self.network)

        extra_vars = {
            "enos_action": "deploy",
            "collector_address": _get_address(self.collector, self.network),
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


class TPGMonitoring(Service):
    def __init__(
        self,
        collector: Host,
        agent: List[Host],
        *,
        ui: Host = None,
        network: Union[str, Tuple] = None,
        remote_working_dir: str = "/builds/monitoring",
    ):
        """Deploy a TPG stack: Telegraf, Prometheus, Grafana.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a monitoring stack on your nodes. Except for
        telegraf agents which will use a binary file for armv7 (FIT/IoT-LAB).

        It's opinionated out of the box but allow for some convenient
        customizations.

        Args:
            collector: :py:class:`enoslib.Host` where the collector
                    will be installed
            ui: :py:class:`enoslib.Host` where the UI will be installed
            agent: list of :py:class:`enoslib.Host` where the agent
                    will be installed
            network: network to use for the monitoring traffic.
                        Agents will send their metrics to the collector using
                        this IP address. In the same way, the ui will use this IP to
                        connect to collector.
                        The IP address is taken from :py:class:`enoslib.Host`, depending
                        on this parameter:
                        - None: IP address = host.address
                        - str: Network role. Get the first IPv4 address available in
                        host.extra_addresses with this network role.
                        - Tuple(str, IPVersion). Network role and protocol version.
                        Get the first IPVersion (ipv4 or ipv6) address in
                        host.extra_ddresses with this network role and version.
                        Note that this parameter depends on calling sync_network_info to
                        fill the extra_addresses structure.
                        Raises an exception if no IP address is found
            remote_working_dir: path to a remote location that
                    will be used as working directory
        """

        # Some initialisation and make mypy happy
        self.collector = collector
        assert self.collector is not None
        self.agent = agent
        assert self.agent is not None
        self.ui = ui if ui else []
        assert self.ui is not None

        self._roles: Roles = {}
        self._roles.update(
            prometheus=[self.collector], telegraf=self.agent, grafana=[self.ui]
        )
        self.remote_working_dir = remote_working_dir
        self.prometheus_port = 9090

        self.network = network

        # We force python3
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}

    def deploy(self):
        """Deploy the monitoring stack"""
        extra_vars = {
            "enos_action": "deploy",
            "collector_type": "prometheus",
            "remote_working_dir": self.remote_working_dir,
            "collector_address": _get_address(self.collector, self.network),
            "collector_port": self.prometheus_port,
            "grafana_address": _get_address(self.ui, self.network),
            "telegraf_targets": [_get_address(h, self.network) for h in self.agent]
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
            "collector_address": _get_address(self.collector, self.network),
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
