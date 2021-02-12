from enoslib.api import play_on, run_command
from typing import List

from ..service import Service
from enoslib.objects import Host


class K3s(Service):
    def __init__(self, master: List[Host], agent: List[Host]):
        """Deploy a K3s cluster.

        Reference:
        https://rancher.com/docs/k3s/latest/en/quick-start/

        This is a basic setup for now. Let us know if something is needed here:
        |chat|

        For instance

        - automatic deployment of the dashboard
        - private registry configuration (e.g G5k registry)
        - ...

        Examples:

            .. literalinclude:: examples/k3s.py
                :language: python
                :linenos:
        """
        self.master = master
        self.agent = agent
        self.roles = dict(master=self.master, agent=self.agent)

    def deploy(self):
        with play_on(roles=self.roles) as p:
            p.apt(name="curl", state="present")

        with play_on(pattern_hosts="master", roles=self.roles, gather_facts=False) as p:
            p.shell("curl -sfL https://get.k3s.io | sh")
        # Getting the token
        result = run_command(
            "cat /var/lib/rancher/k3s/server/node-token",
            pattern_hosts="master",
            roles=self.roles,
        )
        token = result["ok"][self.master[0].alias]["stdout"]
        with play_on(pattern_hosts="agent", roles=self.roles, gather_facts=False) as p:
            p.shell((
                f"curl -sfL https://get.k3s.io |"
                f"K3S_URL=https://{self.master[0].address}:6443 K3S_TOKEN={token} sh"
            ))

    def destroy(self):
        pass

    def backup(self):
        pass
