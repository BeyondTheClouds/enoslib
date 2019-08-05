from enoslib.api import play_on, run_ansible
import os

from ..service import Service

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))

DEFAULT_VARS = {
    "skydive_listen_ip": "0.0.0.0",
    "skydive_deployment_mode": "binary",
    "agent.topology.probes": ["docker"]
}


class Skydive(Service):
    def __init__(self, *, analyzers=None, agents=None, extra_vars=None):
        """Deploy Skydive (see http://skydive.network/).

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a skydive stack on your nodes. It's opinionated
        out of the box but allow for some convenient customizations.

        It is based on the Ansible playbooks found in
        https://github.com/skydive-project/skydive

        Args:
            analyzers (list): list of :py:class:`enoslib.Host` where the
                              skydive analyzers will be installed
            agents (list): list of :py:class:`enoslib.Host` where the agent will
                           be installed
            extra_vars (dict): extra variables to pass to the deployment

        Examples:

            .. literalinclude:: examples/skydive.py
                :language: python
                :linenos:

        """
        self.analyzers = analyzers
        self.agents = agents
        self.skydive = analyzers + agents
        self.roles = {}
        self.roles.update(analyzers=analyzers, agents=agents,
                          skydive=self.skydive)

        self.extra_vars = {}
        self.extra_vars.update(DEFAULT_VARS)
        if extra_vars is not None:
            self.extra_vars.update(extra_vars)

    def deploy(self):
        # Some requirements
        with play_on(pattern_hosts="all", roles=self.roles) as p:
            p.apt(
                display_name="[Preinstall] Installing python-pip",
                name="python-pip",
                state="present",
                update_cache=True,
            )
            p.pip(display_name="[Preinstall] Installing pyyaml", name="pyyaml")
        _playbook = os.path.join(SERVICE_PATH, "skydive", "skydive.yml")
        run_ansible([_playbook], roles=self.roles, extra_vars=self.extra_vars)
