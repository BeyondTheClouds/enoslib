import logging
import os

from jinja2 import Environment, FileSystemLoader
from netaddr import IPNetwork
import vagrant

from enoslib.host import Host
from enoslib.infra.provider import Provider


logger = logging.getLogger(__name__)


TEMPLATE_DIR = os.path.dirname(os.path.realpath(__file__))


class Enos_vagrant(Provider):
    """The provider to use when working with vagrant (local machine).
    """

    def init(self, force_deploy=False):
        """Reserve and deploys the vagrant boxes.

        Args:
            force_deploy (bool): True iff new machines should be started
        """
        machines = self.provider_conf.machines
        networks = self.provider_conf.networks
        _networks = []
        for network in networks:
            ipnet = IPNetwork(network.cidr)
            _networks.append({
                "netpool": list(ipnet)[10:-10],
                "cidr": network.cidr,
                "roles": network.roles,
                "gateway": ipnet.ip
            })

        vagrant_machines = []
        vagrant_roles = {}
        j = 0
        for machine in machines:
            for _ in range(machine.number):
                vagrant_machine = {
                    "name": "enos-%s" % j,
                    "cpu": machine.flavour_desc["core"],
                    "mem": machine.flavour_desc["mem"],
                    "ips": [n["netpool"].pop() for n in _networks],
                }
                vagrant_machines.append(vagrant_machine)
                # Assign the machines to the right roles
                for role in machine.roles:
                    vagrant_roles.setdefault(role, []).append(vagrant_machine)
                j = j + 1

        logger.debug(vagrant_roles)

        loader = FileSystemLoader(searchpath=TEMPLATE_DIR)
        env = Environment(loader=loader, autoescape=True)
        template = env.get_template('Vagrantfile.j2')
        vagrantfile = template.render(machines=vagrant_machines,
                                      provider_conf=self.provider_conf)
        vagrantfile_path = os.path.join(os.getcwd(), "Vagrantfile")
        with open(vagrantfile_path, 'w') as f:
            f.write(vagrantfile)

        # Build env for Vagrant with a copy of env variables (needed by
        # subprocess opened by vagrant
        v_env = dict(os.environ)
        v_env['VAGRANT_DEFAULT_PROVIDER'] = self.provider_conf.backend

        v = vagrant.Vagrant(root=os.getcwd(),
                            quiet_stdout=False,
                            quiet_stderr=False,
                            env=v_env)
        if force_deploy:
            v.destroy()
        v.up()
        v.provision()
        roles = {}
        for role, machines in vagrant_roles.items():
            for machine in machines:
                keyfile = v.keyfile(vm_name=machine['name'])
                port = v.port(vm_name=machine['name'])
                address = v.hostname(vm_name=machine['name'])
                roles.setdefault(role, []).append(
                    Host(address,
                         alias=machine['name'],
                         user=self.provider_conf.user,
                         port=port,
                         keyfile=keyfile))

        networks = [{
            'cidr': str(n["cidr"]),
            'start': str(n["netpool"][0]),
            'end': str(n["netpool"][-1]),
            'dns': '8.8.8.8',
            'gateway': str(n["gateway"]),
            'roles': n["roles"]
            } for n in _networks]
        logger.debug(roles)
        logger.debug(networks)

        return (roles, networks)

    def destroy(self):
        """Destroy all vagrant box involved in the deployment."""
        v = vagrant.Vagrant(root=os.getcwd(),
                            quiet_stdout=False,
                            quiet_stderr=True)
        v.destroy()
