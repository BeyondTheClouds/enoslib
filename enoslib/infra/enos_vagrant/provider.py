from enoslib.host import Host
from enoslib.utils import get_roles_as_list
from netaddr import IPNetwork
from jinja2 import Environment, FileSystemLoader
from enoslib.infra.provider import Provider

import logging
import os
import vagrant

logger = logging.getLogger(__name__)

#: The default configuration of the vagrant provider
DEFAULT_CONFIG = {
    "backend": "virtualbox",
    "box": "bento/debian-9",
    "user": "root",
}

#: Sizes of the machines available for the configuration
FLAVORS = {
    "tiny": {
        "cpu": 1,
        "mem": 512
    },
    "small": {
        "cpu": 1,
        "mem": 1024
    },
    "medium": {
        "cpu": 2,
        "mem": 2048
    },
    "big": {
        "cpu": 3,
        "mem": 3072,
    },
    "large": {
        "cpu": 4,
        "mem": 4096
    },
    "extra-large": {
        "cpu": 6,
        "mem": 6144
    }
}

TEMPLATE_DIR = os.path.dirname(os.path.realpath(__file__))

# This is the schema for the abstract description of the resources
SCHEMA = {
    "type": "object",
    "properties": {
        "resources": {"$ref": "#/resources"}
    },
    "additionalProperties": True,
    "required": ["resources"],

    "resources": {
        "title": "Resource",

        "type": "object",
        "properties": {
            "machines": {"type": "array", "items": {"$ref": "#/machine"}},
            "networks": {
                "type": "array",
                "items": {"$ref": "#/network"},
                "uniqueItems": True},
        },
        "additionalProperties": False,
        "required": ["machines"]
    },

    "machine": {
        "title": "Compute",
        "type": "object",
        "properties": {
            "anyOf": [
                {"roles": {"type": "array", "items": {"type": "string"}}},
                {"role": {"type": "string"}}
            ],
            "flavor": {"type": "string"},
            "number": {"type": "number"},
            "networks": {"type": "array", "items": {"type": "string"}}
        },
        "required": [
            "number",
            "flavor"
        ]
    }
}


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
    """The provider to use when working with vagrant (local machine).

        Examples:

            .. code-block:: yaml

                # provider_conf in yaml
                ---
                backend: virtualbox
                user: root
                box: debian/jessie64
                resources:
                    machines:
                    - roles: [telegraf]
                        flavor: tiny
                        number: 1
                        networks: [control_network, internal_network]
                    - roles:
                        - control
                        - registry
                        - prometheus
                        - grafana
                        - telegraf
                        flavor: medium
                        number: 1
                        networks: [control_network]
    """

    def init(self, force_deploy=False):
        """Reserve and deploys the vagrant boxes.

        Args:
            force_deploy (bool): True iff new machines should be started

        The above ``provider_conf`` will return a tuple (roles, networks)
        where:

            .. code-block:: yaml

                roles:
                  telegraf:
                    - !!python/object:enoslib.host.Host
                      address: 127.0.0.1
                      alias: enos-1
                      extra:
                        enos_devices: [eth1, eth2]
                        control_network: eth1
                        internal_network: eth2
                      keyfile: ...
                      port: '2205'
                      user: root
                    - !!python/object:enoslib.host.Host
                      address: 127.0.0.1
                      alias: enos-0
                      extra:
                        enos_devices: [eth1, eth2]
                        control_network: eth1
                        internal_network: eth2
                      keyfile: ...
                      port: '2204'
                      user: root
                  control:
                    # machine with role control

               networks:
                 - cidr: 192.168.142.0/24
                   dns: 8.8.8.8
                   end: 192.168.142.243
                   gateway: 192.168.142.1
                   roles: [control_network]
                   start: 192.168.142.10
                 - cidr: 192.168.143.0/24
                   dns: 8.8.8.8
                   end: 192.168.143.244
                   gateway: 192.168.143.1
                   roles: [internal_network]
                   start: 192.168.143.10
        """
        # Arbitrary net pool size
        slash_24 = [142 + x for x in range(0, 100)]
        slash_24 = [IPNetwork("192.168.%s.1/24" % x) for x in slash_24]
        net_pool = [list(x)[10:-10] for x in slash_24]

        machines = self.provider_conf["resources"]["machines"]
        # build the mapping network_name -> pool
        networks = [machine.get("networks", []) for machine in machines]
        # flatten and build the set of networks
        networks = set([item for sublist in networks for item in sublist])
        networks = dict(zip(networks, net_pool))
        vagrant_machines = []
        vagrant_roles = {}
        j = 0
        for machine in machines:
            for _ in range(machine["number"]):
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
        v_env['VAGRANT_DEFAULT_PROVIDER'] = self.provider_conf['backend']

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
                         user=self.provider_conf['user'],
                         port=port,
                         keyfile=keyfile))

        networks = [{
            'cidr': str(ipnet.cidr),
            'start': str(pool[0]),
            'end': str(pool[-1]),
            'dns': '8.8.8.8',
            'gateway': str(ipnet.ip),
            'roles': [net]
            } for ipnet, pool, net in zip(
                slash_24,
                net_pool[0: len(networks.keys())], networks.keys())]
        logger.debug(roles)
        logger.debug(networks)
        return (roles, networks)

    def destroy(self):
        """Destroy all vagrant box involved in the deployment."""
        v = vagrant.Vagrant(root=os.getcwd(),
                            quiet_stdout=False,
                            quiet_stderr=True)
        v.destroy()

    def default_config(self):
        """
        Default configuration
        """
        return DEFAULT_CONFIG

    def schema(self):
        """Returns the schema of the provider config."""
        return SCHEMA
