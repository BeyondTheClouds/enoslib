from ipaddress import ip_interface
import logging
import os

from jinja2 import Environment, FileSystemLoader
from netaddr import IPNetwork

import vagrant

from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.infra.provider import Provider

from .constants import DEFAULT_NAME_PREFIX

logger = logging.getLogger(__name__)


TEMPLATE_DIR = os.path.dirname(os.path.realpath(__file__))


def check():
    # At this point this should be ok
    if vagrant.get_vagrant_executable() is None:
        return [("access", False, "Vagrant executable not found")]
    else:
        return [("access", True, "Looks good so far")]


class VagrantNetwork(DefaultNetwork):
    pass


class Enos_vagrant(Provider):
    """The provider to use when working with vagrant (local machine)."""

    def init(self, force_deploy=False, **kwargs):
        """Reserve and deploys the vagrant boxes.

        Args:
            force_deploy (bool): True iff new machines should be started
        """
        machines = self.provider_conf.machines
        networks = self.provider_conf.networks
        _networks = []
        for network in networks:
            ipnet = IPNetwork(network.cidr)
            _networks.append(
                {
                    "netpool": list(ipnet)[10:-10],
                    "cidr": network.cidr,
                    "roles": network.roles,
                    "gateway": ipnet.ip,
                }
            )

        vagrant_machines = []
        vagrant_roles = {}
        global_prefix = self.provider_conf.name_prefix or DEFAULT_NAME_PREFIX
        for counter, machine in enumerate(machines):
            prefix = (
                machine.name_prefix
                if machine.name_prefix
                else f"{global_prefix}-{counter}"
            )
            for index in range(machine.number):
                suffix = f"-{index + 1}" if machine.number > 1 else ""
                vagrant_machine = {
                    "name": f"{prefix}{suffix}",
                    "cpu": machine.flavour_desc["core"],
                    "mem": machine.flavour_desc["mem"],
                    "ips": [n["netpool"].pop() for n in _networks],
                }
                vagrant_machines.append(vagrant_machine)
                # Assign the machines to the right roles
                for role in machine.roles:
                    vagrant_roles.setdefault(role, []).append(vagrant_machine)

        logger.debug(vagrant_roles)

        loader = FileSystemLoader(searchpath=TEMPLATE_DIR)
        env = Environment(loader=loader, autoescape=True)
        template = env.get_template("Vagrantfile.j2")
        vagrantfile = template.render(
            machines=vagrant_machines, provider_conf=self.provider_conf
        )
        vagrantfile_path = os.path.join(os.getcwd(), "Vagrantfile")
        with open(vagrantfile_path, "w") as f:
            f.write(vagrantfile)

        # Build env for Vagrant with a copy of env variables (needed by
        # subprocess opened by vagrant
        v_env = dict(os.environ)
        v_env["VAGRANT_DEFAULT_PROVIDER"] = self.provider_conf.backend

        v = vagrant.Vagrant(
            root=os.getcwd(), quiet_stdout=False, quiet_stderr=False, env=v_env
        )
        if force_deploy:
            v.destroy()

        v.up()
        v.provision()
        roles = Roles()
        for role, machines in vagrant_roles.items():
            for machine in machines:
                keyfile = v.keyfile(vm_name=machine["name"])
                port = v.port(vm_name=machine["name"])
                address = v.hostname(vm_name=machine["name"])
                roles[role] += [
                    Host(
                        address,
                        alias=machine["name"],
                        user=self.provider_conf.user,
                        port=port,
                        keyfile=keyfile,
                    )
                ]
        networks = Networks()
        for network in _networks:
            for role in network["roles"]:
                vagrant_net = VagrantNetwork(
                    address=str(ip_interface(network["cidr"]).network),
                    gateway=str(network["gateway"]),
                    dns="8.8.8.8",
                )
                networks[role] += [vagrant_net]

        logger.debug(roles)
        logger.debug(networks)

        return (roles, networks)

    def destroy(self, wait=False):
        """Destroy all vagrant box involved in the deployment."""
        v = vagrant.Vagrant(root=os.getcwd(), quiet_stdout=False, quiet_stderr=True)
        v.destroy()

    def offset_walltime(self, difference: int):
        pass
