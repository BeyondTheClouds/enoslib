import os
from typing import List, Dict

from enoslib.api import (
    play_on,
    run_ansible,
    __python3__,
    __docker__,
)
from enoslib.types import Host

from ..service import Service

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

DEFAULT_VARS = {
    "skydive_listen_ip": "0.0.0.0",
    "skydive_deployment_mode": "container",
    "agent.topology.probes": ["docker"],
    # we'll inject our own topology
    # there a skydive_fabric variable to do that
    "skydive_auto_fabric": "no",
    # force python3
    "ansible_python_interpreter": "/usr/bin/python3"
}


class Skydive(Service):
    def __init__(
        self,
        *,
        analyzers: List[Host] = None,
        agents: List[Host] = None,
        networks: List[Host] = None,
        priors: List[play_on] = [__python3__, __docker__],
        extra_vars: Dict = None,
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
        self.analyzers = analyzers if analyzers is not None else []
        assert(self.analyzers is not None)
        self.agents = agents if agents is not None else []
        assert(self.agents is not None)
        self.skydive = self.analyzers + self.agents
        self.roles: Dict = {}
        self.networks = networks
        self.priors = priors
        self.roles.update(analyzers=analyzers, agents=agents, skydive=self.skydive)

        self.extra_vars = {}
        self.extra_vars.update(DEFAULT_VARS)
        if extra_vars is not None:
            self.extra_vars.update(extra_vars)

        # build the network topology
        self.fabric_opts = self.build_fabric()
        if self.fabric_opts:
            self.extra_vars.update(skydive_fabric=self.fabric_opts)

    def build_fabric(self):
        def fabric_for_role(network_role, desc):
            fabric = []
            for agent in self.agents:
                device = agent.extra.get("%s_dev" % network_role)
                if device is not None:
                    infos = "cidr=%s, gateway=%s, dns=%s" % (
                        desc["cidr"],
                        desc["gateway"],
                        desc["dns"],
                    )
                    infos = "%s, roles=%s" % (infos, "-".join(desc["roles"]))
                    local_port = "%s-%s" % (network_role, int(len(fabric) / 2))
                    fabric.append("%s[%s] -> %s" % (desc["cidr"], infos, local_port))
                    fabric.append(
                        "%s -> *[Type=host, Hostname=%s]/%s"
                        % (local_port, agent.alias, device)
                    )
            return fabric

        fabric = []
        if self.networks is None:
            return fabric

        for n in self.networks:
            roles = n["roles"]
            for role in roles:
                # we use the first role to be able to get the associated device
                fabric.extend(fabric_for_role(role, n))
                break
        return fabric

    def deploy(self):
        """Deploy Skydive service."""
        # Some requirements
        with play_on(pattern_hosts="all", roles=self.roles, priors=self.priors) as p:
            p.pip(display_name="[Preinstall] Installing pyyaml", name="pyyaml")
        _playbook = os.path.join(SERVICE_PATH, "skydive", "skydive.yml")
        run_ansible([_playbook], roles=self.roles, extra_vars=self.extra_vars)
