from enoslib.api import actions, run
from typing import Iterable

from ..service import Service
from enoslib.objects import Host, Roles


GUARD_DASHBOARD = (
    "k3s kubectl get service" " -n kubernetes-dashboard kubernetes-dashboard"
)

CREATE_DASHBOARD = (
    "k3s kubectl create"
    " -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.5.1/aio/deploy/recommended.yaml"  # noqa
)

ADMIN_USER = """
apiVersion: v1
kind: ServiceAccount
metadata:
  name: admin-user
  namespace: kubernetes-dashboard
"""
GUARD_ADMIN_USER = "k3s kubectl get serviceaccounts -n kubernetes-dashboard admin-user"
CREATE_ADMIN_USER = "k3s kubectl create -f dashboard.admin-user.yml"

ADMIN_USER_ROLE = """
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: admin-user
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
- kind: ServiceAccount
  name: admin-user
  namespace: kubernetes-dashboard
"""
GUARD_ADMIN_USER_ROLE = (
    "k3s kubectl get clusterrolebindings -n kubernetes-dashboard admin-user"
)
CREATE_ADMIN_USER_ROLE = "k3s kubectl create -f dashboard.admin-user-role.yml"

CREATE_PROXY = "kubectl proxy --address='0.0.0.0' --accept-hosts='.*'"
# use grep {CREATE_PROXY}
KEY = "kubectl proxy"
GUARD_PROXY = f"ps aux | grep '{KEY}' | grep -v '{KEY}'"


class K3s(Service):
    def __init__(self, master: Iterable[Host], agent: Iterable[Host]):
        """Deploy a single K3s cluster.

        Note:

        In order to deploy multiple (independent) nodes, please do so by
        creating multiple instances of this service.

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
        self.roles = Roles(master=self.master, agent=self.agent)

    def deploy(self):
        with actions(roles=self.roles) as p:
            p.apt(name="curl", state="present")

        with actions(roles=self.roles["master"], gather_facts=False) as p:
            p.shell(
                "curl -sfL https://get.k3s.io | sh", task_name="[master] Deploying K3s"
            )
        # Getting the token
        result = run(
            "cat /var/lib/rancher/k3s/server/node-token",
            pattern_hosts="master",
            roles=self.roles,
            task_name="[master] Getting k3s token",
        )

        token = result[0].stdout
        with actions(roles=self.roles["agent"], gather_facts=False) as p:
            cmd = f"K3S_URL=https://{self.master[0].address}:6443 K3S_TOKEN={token} sh"
            p.shell(
                (f"curl -sfL https://get.k3s.io | {cmd}"),
                task_name="[agent] Deploying K3s on agent",
            )
        with actions(roles=self.roles["master"], gather_facts=False) as p:
            # deploy dashboard
            # https://rancher.com/docs/k3s/latest/en/installation/kube-dashboard/
            p.shell(
                f"{GUARD_DASHBOARD} || {CREATE_DASHBOARD}",
                task_name="[master] Installing the dashboard",
            )
            p.copy(dest="dashboard.admin-user.yml", content=ADMIN_USER)
            p.copy(dest="dashboard.admin-user-role.yml", content=ADMIN_USER_ROLE)
            p.shell(f"{GUARD_ADMIN_USER} || {CREATE_ADMIN_USER}")
            p.shell(f"{GUARD_ADMIN_USER_ROLE} || {CREATE_ADMIN_USER_ROLE}")
            p.shell(
                "k3s kubectl -n kubernetes-dashboard describe secret admin-user-token | grep '^token'",  # noqa
                task_name="token",
            )
            p.shell(f"{GUARD_PROXY} || {CREATE_PROXY}", background=True)
        # return dashboard bearer token
        return p.results.filter(task="token")[0].stdout

    def destroy(self):
        pass

    def backup(self):
        pass
