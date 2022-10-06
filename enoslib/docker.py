"""Manage remote docker containers as first class citizens.

A possible workflow would be to start your containers using the method of
your choice and build the list of available dockers using the
:py:func:`enoslib.docker.get_dockers` function.

A ``DockerHost`` is a specialization of a ``Host`` and thus can be fed into
any Host related operations (play_on, run_command...) [#docker0]_. Hosts
datastructure in enoslib are tied somehow to Ansible. DockerHost is shaped so
that the docker connection plugin can run. So we inject at build time the
necessary connection options (``ansible_connection=docker``,
``ansible_docker_extra_args="-H <remote_docker>"``).

Connections to remote docker daemons can be made using different
protocols [#docker1]_.

- Using ssh: requires ssh access to remote host but
    can go through a bastion host if .ssh/config is configured correctly.
    Note that the docker client must be available.
- Using raw tcp: requires to reach the remote docker daemon (e.g. be inside
    g5k). Note that in this case the remote socket must be exposed.

Additionally, the structure is compatible with mitogen and its delegation model
[#docker2]_ which can improve the performance. Note that the facts from the
host machines (where the docker daemon runs) needs to be gathered. One way to
ensure this is to explicitly gather the facts from such hosts.

.. topic:: Links

    .. [#docker0] https://en.wikipedia.org/wiki/Liskov_substitution_principle
    .. [#docker1] https://docs.docker.com/engine/reference/commandline/dockerd
    .. [#docker2] https://mitogen.networkgenomics.com/ansible_detailed.html

Example:

    .. literalinclude:: examples/advanced_docker.py
        :language: python
        :linenos:
"""

import json
from typing import List, Mapping, Optional

from enoslib.api import run_command, get_hosts
from enoslib.objects import Host, Roles


class DockerHost(Host):
    """A kind of host reachable using docker protocol.

    Args:
        alias: **unique** name across the deployment
        name : name of the docker container on the remote hosts
        host : the host where the container can be found
        proto: how to connect to the remote host
                (DockerHost.PROTO_TCP/DockerHost.PROTO_SSH)
                [Default DockerHost.PROTO_SSH]
        state: dict representing the state as returned by ``docker inspect``
    """

    PROTO_SSH = "ssh"
    PROTO_TCP = "tcp"

    def __init__(
        self,
        alias: str,
        container_name: str,
        host: Host,
        proto: Optional[str] = None,
        state: Optional[Mapping] = None,
    ):
        self.remote = host.address
        if proto is None:
            proto = self.PROTO_SSH
        self.proto = proto
        if self.proto not in [self.PROTO_SSH, self.PROTO_TCP]:
            raise ValueError(f"proto must be in {[self.PROTO_SSH, self.PROTO_TCP]}")

        if host.user:
            self.remote = f"{host.user}@{host.address}"
        else:
            self.remote = f"{host.address}"

        # Optionally keep the internal state (return by docker inspect)
        # Note that currently we don't provide, any consistency guarantee.
        self._state = {} if state is None else state
        super().__init__(
            container_name,
            alias=alias,
            user=host.user,
            keyfile=host.keyfile,
            extra=dict(
                ansible_connection="docker",
                ansible_docker_extra_args=f"-H {proto}://{self.remote}",
                mitogen_via=f"{self.remote}",
            ),
        )

    @classmethod
    def from_state(cls, state: Mapping, host: Host):
        """Build a DockerHost from a state json as returned by docker inspect."""
        container_name = state["Name"]
        alias = f"{container_name}-{host.alias}"
        return cls(alias, container_name, host, state=state)


def get_dockers(
    roles: Roles, pattern_hosts: str = "*", container_name: str = ".*"
) -> List[DockerHost]:
    """Get remote dockers hosts.

    Args:
        roles: the roles as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        pattern_hosts: pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        container_name: name of the containers to look for. Regexp are
            supported as in filter option of docker inspect.

    Returns:
        List of DockerHost matching the passed container_name
    """
    docker_hosts = []
    result = run_command(
        f"docker ps -q --filter name={container_name} | xargs docker inspect",
        pattern_hosts=pattern_hosts,
        roles=roles,
        on_error_continue=True,
        gather_facts=False,
    )
    # parsing the results
    for r in result:
        dockers = json.loads(r.stdout)
        host = get_hosts(roles, r.host)[0]
        for docker in dockers:
            docker_host = DockerHost.from_state(docker, host)
            docker_hosts.append(docker_host)
    return docker_hosts
