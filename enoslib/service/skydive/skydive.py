import os
from itertools import chain
from typing import Iterable, List, Dict, Optional

from enoslib.api import (
    actions,
    run_ansible,
    __python3__,
    __docker__,
)
from enoslib.objects import Host, Network, Roles
from ..service import Service

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

DEFAULT_VARS = {
    "skydive_listen_ip": "0.0.0.0",
    "skydive_deployment_mode": "container",
    "agent.topology.probes": ["docker"],
    # we'll inject our own topology
    # there a skydive_fabric variable to do that
    "skydive_auto_fabric": "no",
}


class Skydive(Service):
    def destroy(self):
        print("Skydive.destroy() is not implemented")

    def backup(self):
        print("Skydive.backup() is not implemented")

    def __init__(
        self,
        *,
        analyzers: Optional[Iterable[Host]] = None,
        agents: Optional[Iterable[Host]] = None,
        networks: Optional[Iterable[Network]] = None,
        priors: Optional[List[actions]] = None,
        extra_vars: Optional[Dict] = None,
    ):
        """Deploy Skydive (see http://skydive.network/).

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a skydive stack on your nodes. It's opinionated
        out of the box but allow for some convenient customizations.

        It is based on the Ansible playbooks found in
        https://github.com/skydive-project/skydive

        Args:
            analyzers: list of :py:class:`enoslib.Host` where the
                              skydive analyzers will be installed
            agents: list of :py:class:`enoslib.Host` where the agent will
                           be installed
            networks: list of networks as returned by a provider. This is
                             visually see them in the interface
            priors: prior to apply before deploying this service
            extra_vars (dict): extra variables to pass to the deployment

        Examples:

            .. literalinclude:: examples/skydive.py
                :language: python
                :linenos:

        """
        self.analyzers: Iterable[Host] = analyzers if analyzers is not None else []
        assert self.analyzers is not None
        self.agents: List[Host] = list(set(agents)) if agents is not None else []
        assert self.agents is not None
        self.skydive: Iterable[Host] = chain(self.analyzers, self.agents)
        self.networks: Optional[Iterable[Network]] = networks
        self.priors = priors if priors is not None else [__python3__, __docker__]
        self.roles = Roles(analyzers=analyzers, agents=agents, skydive=self.skydive)

        self.extra_vars: Dict = DEFAULT_VARS
        if extra_vars is not None:
            self.extra_vars.update(extra_vars)

        # build the network topology
        self.fabric_opts = self.build_fabric()
        if self.fabric_opts:
            self.extra_vars.update(skydive_fabric=self.fabric_opts)

    def build_fabric(self) -> List[str]:
        def fabric_for_role(network):
            fabric: List[str] = []
            for agent in self.agents:
                devices = agent.filter_interfaces([network])
                for device in devices:
                    if device is not None:
                        infos = f"cidr={network.network}"
                        infos = f"{infos}, roles={'-'.join(network.roles)}"
                        local_port = f"{'-'.join(network.roles)}-{int(len(fabric) / 2)}"
                        fabric.append(f"{network.network}[{infos}] -> {local_port}")
                        fabric.append(
                            f"{local_port} -> *[Type=host, Hostname={agent.alias}]/{device}"  # noqa
                        )
            return fabric

        fabric: List = []
        if self.networks is None:
            return fabric

        for network in self.networks:
            # we use the first role to be able to get the associated device
            fabric.extend(fabric_for_role(network))

        return fabric

    def deploy(self):
        """Deploy Skydive service."""
        # Some requirements
        with actions(
            roles=self.roles,
            priors=self.priors,
            extra_vars=self.extra_vars,
        ) as p:
            p.pip(task_name="[Preinstall] Installing pyyaml", name="pyyaml")
        _playbook = os.path.join(SERVICE_PATH, "skydive", "skydive.yml")
        run_ansible([_playbook], roles=self.roles, extra_vars=self.extra_vars)
