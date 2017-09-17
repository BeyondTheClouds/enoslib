from enoslib.constants import PROVIDER_DIR
from enoslib.host import Host
from netaddr import IPNetwork
from jinja2 import Environment, FileSystemLoader
from provider import Provider

import logging
import os
import vagrant

FLAVORS = {
    'tiny': {
        'cpu': 1,
        'mem': 512
    },
    'small': {
        'cpu': 1,
        'mem': 1024
    },
    'medium': {
        'cpu': 2,
        'mem': 2048
    },
    'big': {
        'cpu': 3,
        'mem': 3072,
    },
    'large': {
        'cpu': 4,
        'mem': 4096
    },
    'extra-large': {
        'cpu': 6,
        'mem': 6144
    }
}

TEMPLATE_DIR = PROVIDER_DIR


def get_roles_as_list(desc):
    roles = desc.get("role", [])
    if roles:
        roles = [roles]
    roles.extend(desc.get("roles", []))
    return roles


# NOTE(msimonin) add provider config validation
# for now :
# provider_conf:
#   backend:
#   box:
#   machines:
#     - size: (enum)
#       number:
#       role:
#       (or roles:[...])
#       networks: [network_names]
class Enos_vagrant(Provider):
    def init(self, provider_conf, force_deploy=False):
        """enos up
        Read the resources in the configuration files. Resource claims must be
        grouped by sizes according to the predefined SIZES map.
        """
        # Arbitrary net pool size
        slash_24 = [142 + x for x in range(0, 100)]
        slash_24 = [IPNetwork("192.168.%s.1/24" % x) for x in slash_24]
        net_pool = [list(x)[10:-10] for x in slash_24]

        machines = provider_conf["machines"]
        # build the mapping network_name -> pool
        networks = [set(machine["networks"]) for machine in machines]
        networks = reduce(set.union, networks)
        networks = dict(zip(networks, net_pool))
        vagrant_machines = []
        vagrant_roles = {}
        j = 0
        for machine in machines:
            for i in range(machine["number"]):
                vagrant_machine = {
                    "name": "enos-%s" % j,
                    "cpu": FLAVORS[machine["flavor"]]["cpu"],
                    "mem": FLAVORS[machine["flavor"]]["mem"],
                    "ips": [networks[n].pop() for n in machine["networks"]],
                }
                vagrant_machines.append(vagrant_machine)
                # Assign the machines to the right roles
                for role in get_roles_as_list(machine):
                    vagrant_roles.setdefault(role, []).append(vagrant_machine)
                j = j + 1

        logging.debug(vagrant_roles)

        loader = FileSystemLoader(searchpath=TEMPLATE_DIR)
        env = Environment(loader=loader)
        template = env.get_template('Vagrantfile.j2')
        vagrantfile = template.render(machines=vagrant_machines,
                provider_conf=provider_conf)
        vagrantfile_path = os.path.join(os.getcwd(), "Vagrantfile")
        with open(vagrantfile_path, 'w') as f:
            f.write(vagrantfile)

        # Build env for Vagrant with a copy of env variables (needed by
        # subprocess opened by vagrant
        v_env = dict(os.environ)
        v_env['VAGRANT_DEFAULT_PROVIDER'] = provider_conf['backend']

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
                         user=provider_conf['user'],
                         port=port,
                         keyfile=keyfile))

        networks = [{
            'cidr': str(ipnet.cidr),
            'start': str(pool[0]),
            'end': str(pool[-1]),
            'dns': '8.8.8.8',
            'gateway': str(ipnet.ip)
            } for ipnet, pool in zip(
                slash_24,
                net_pool[0: len(networks.keys())])]
        logging.debug(roles, networks)
        return (roles, networks)

    def destroy(self, env):
        v = vagrant.Vagrant(root=os.getcwd(),
                            quiet_stdout=False,
                            quiet_stderr=True)
        v.destroy()

    def default_config(self):
        return {
            'backend': 'virtualbox',
            'box': 'debian/jessie64',
            'user': 'root',
            'interfaces': ('eth1', 'eth2')
        }
