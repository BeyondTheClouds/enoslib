import os

from jsonschema import validate

from enoslib.api import run_ansible
from enoslib.objects import Roles
from ..service import Service


REGISTRY_OPTS = {"type": "none"}
SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class Docker(Service):
    SCHEMA = {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "type": {"const": "external"},
                    "ip": {"type": "string"},
                    "port": {"type": "number"},
                },
                "additionalProperties": False,
                "required": ["type", "ip", "port"],
            },
            {
                "type": "object",
                "properties": {
                    "type": {"const": "internal"},
                    "port": {"type": "number", "default": 5000},
                },
                "additionalProperties": False,
                "required": ["type"],
            },
            {
                "type": "object",
                "properties": {"type": {"const": "none"}},
                "additionalProperties": False,
                "required": ["type"],
            },
        ]
    }

    def __init__(
        self,
        *,
        agent=None,
        registry=None,
        registry_opts=None,
        bind_var_docker=None,
        swarm=False
    ):
        """Deploy docker agents on the nodes and registry cache(optional)

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy docker and optionally a registry on your nodes.

        If an NVidia GPU is detected on a node, the `nvidia-container-toolkit` will be
        also installed automatically.
        see https://docs.nvidia.com/datacenter/cloud-native/

        Examples:

            .. code-block:: python

                # Use an internal registry on the first agent
                docker = Docker(agent=roles["agent"])

                # Use an internal registry on the specified host
                docker = Docker(agent=roles["agent"],
                                registry=roles["registry"])

                # Use an external registry
                docker = Docker(agent=roles["compute"] + roles["control"],
                                registry_opts = {"type": "external",
                                                 "ip": "192.168.42.1",
                                                 "port": 4000})

            .. literalinclude:: examples/docker.py
                :language: python
                :linenos:


        Args:
            agent (list): list of :py:class:`enoslib.Host` where the docker
                agent will be installed
            registry (list): list of :py:class:`enoslib.Host` where the docker
                registry will be installed.
            registry_opts (dict): registry options. The dictionary must comply
                with the schema.
            bind_var_docker (str): If set the default docker state directory
                (/var/lib/docker/) will be bind mounted in this
                directory. The rationale is that on Grid'5000, there isn't much
                disk space on /var/lib by default. Set it to False to disable
                the fallback to the default location.
            swarm (bool): Whether a docker swarm needs to be created over the agents.
                The first agent will be taken as the swarm master.
        """
        # TODO: use a decorator for this purpose
        if registry_opts:
            validate(instance=registry_opts, schema=self.SCHEMA)

        self.agent = agent if agent else []
        self.registry_opts = registry_opts if registry_opts else REGISTRY_OPTS
        if self.registry_opts["type"] == "none":
            self.registry = []
        if self.registry_opts["type"] == "external":
            self.registry = []
        if self.registry_opts["type"] == "internal" or registry is not None:
            _registry = registry[0] if registry else agent[0]
            self.registry = [_registry]
            self.registry_opts["type"] = "internal"
            self.registry_opts["ip"] = _registry.address
            if self.registry_opts.get("port") is None:
                self.registry_opts["port"] = 5000

        self.bind_var_docker = bind_var_docker
        self.swarm = swarm
        self._roles = Roles(
            {
                "agent": self.agent,
                "registry": self.registry,
                "swarm-manager": [self.agent[0]],
                "swarm-node": self.agent,
            }
        )

    def deploy(self):
        """Deploy docker and optionally a docker registry cache."""
        _playbook = os.path.join(SERVICE_PATH, "docker.yml")
        extra_vars = {
            "registry": self.registry_opts,
            "enos_action": "deploy",
            "swarm": self.swarm,
        }
        if self.bind_var_docker:
            # In the Ansible playbook, undefined means no binding
            extra_vars.update(bind_var_docker=self.bind_var_docker)
        run_ansible([_playbook], roles=self._roles, extra_vars=extra_vars)

    def destroy(self):
        """(Not implemented) Destroy docker

        Feel free to share your ideas.
        """
        pass

    def backup(self):
        """(Not implemented) Backup docker.

        Feel free to share your ideas.
        """
        pass
