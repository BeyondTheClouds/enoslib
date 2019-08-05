from enoslib.api import run_ansible
import os

from .service import Service, SERVICE_PATH


DEFAULT_VARS = {
    "skydive_listen_ip": "0.0.0.0",
    "skydive_deployment_mode": "binary",
    "agent.topology.probes": ["docker"]
}


class Skydive(Service):
    def __init__(self, *, analyzers=None, agents=None, extra_vars=None):
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
        _playbook = os.path.join(SERVICE_PATH, "skydive", "skydive.yml")
        run_ansible([_playbook], roles=self.roles, extra_vars=self.extra_vars)


