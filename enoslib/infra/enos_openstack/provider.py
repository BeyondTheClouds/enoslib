# -*- coding: utf-8 -*-
import ipaddress
import logging
from operator import itemgetter
import os
import re
import time

from glanceclient import client as glance
from keystoneauth1.identity import v2, v3
from keystoneauth1 import session
from neutronclient.neutron import client as neutron
from novaclient import client as nova

from enoslib.host import Host
from enoslib.infra.utils import pick_things, mk_pools
from enoslib.infra.provider import Provider
from .constants import (NOVA_VERSION, GLANCE_VERSION, DEFAULT_PREFIX,
                        SECGROUP_NAME, ROUTER_NAME)


logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def get_session():
    """Build the session object."""
    # NOTE(msimonin): We provide only a basic support which focus
    # Chameleon cloud and its rc files
    if os.environ.get("OS_IDENTITY_API_VERSION") == "3":
        logging.info("Creating a v3 Keystone Session")
        auth = v3.Password(
            auth_url=os.environ["OS_AUTH_URL"],
            username=os.environ["OS_USERNAME"],
            password=os.environ["OS_PASSWORD"],
            project_id=os.environ["OS_PROJECT_ID"],
            user_domain_name=os.environ["OS_USER_DOMAIN_NAME"]
        )

    else:
        logging.info("Creating a v2 Keystone Session")
        auth = v2.Password(
            auth_url=os.environ["OS_AUTH_URL"],
            username=os.environ["OS_USERNAME"],
            password=os.environ["OS_PASSWORD"],
            tenant_id=os.environ["OS_TENANT_ID"])

    return session.Session(auth=auth)


def check_glance(session, image_name):
    """Check that the base image is available.

    Fails if the base image isn't added.
    This means the image should be added manually.
    """
    gclient = glance.Client(GLANCE_VERSION, session=session,
                            region_name=os.environ['OS_REGION_NAME'])
    images = gclient.images.list()
    name_ids = [{'name': i['name'], 'id': i['id']} for i in images]
    if image_name not in list(map(itemgetter('name'), name_ids)):
        logger.error("[glance]: Image %s is missing" % image_name)
        raise Exception("Image %s is missing" % image_name)
    else:
        image = [i for i in name_ids if i['name'] == image_name]
        image_id = image[0]['id']
        logger.info("[glance]: Using image %s:%s" % (image_name, image_id))
    return image_id


def check_flavors(session):
    """Build the flavors mapping

    returns the mappings id <-> flavor
    """
    nclient = nova.Client(NOVA_VERSION, session=session,
                          region_name=os.environ['OS_REGION_NAME'])
    flavors = nclient.flavors.list()
    to_id = dict(list(map(lambda n: [n.name, n.id], flavors)))
    to_flavor = dict(list(map(lambda n: [n.id, n.name], flavors)))
    return to_id, to_flavor


def check_network(session, configure_network, network, subnet,
                  dns_nameservers=None, allocation_pool=None):
    """Check the network status for the deployment.

    If needed, it creates a dedicated :
        * private network /subnet
        * router between this network and the external network
    """
    nclient = neutron.Client('2', session=session,
                             region_name=os.environ['OS_REGION_NAME'])

    # Check the security groups
    secgroups = nclient.list_security_groups()['security_groups']
    secgroup_name = SECGROUP_NAME
    if secgroup_name not in list(map(itemgetter('name'), secgroups)):
        secgroup = {'name': secgroup_name,
                    'description': 'Enos Security Group'}
        res = nclient.create_security_group({'security_group': secgroup})
        secgroup = res['security_group']
        logger.info("[neutron]: %s security group created" % secgroup_name)
        # create the rules
        tcp = {'protocol': 'tcp',
               'direction': 'ingress',
               'port_range_min': '1',
               'port_range_max': '65535',
               'security_group_id': secgroup['id']}
        icmp = {'protocol': 'icmp',
                'direction': 'ingress',
                'security_group_id': secgroup['id']}
        nclient.create_security_group_rule({'security_group_rule': tcp})
        logger.info("[neutron]: %s rule (all tcp) created" % secgroup_name)
        nclient.create_security_group_rule({'security_group_rule': icmp})
        logger.info("[neutron]: %s rule (all icmp) created" % secgroup_name)
    else:
        logger.info("[neutron]: Reusing security-groups %s " % secgroup_name)

    networks = nclient.list_networks()['networks']
    network_name = network['name']
    if network_name not in list(map(itemgetter('name'), networks)):
        network = {'name': network_name}
        res = nclient.create_network({'network': network})
        network = res['network']
        logger.info("[neutron]: %s network created" % network_name)
    else:
        network = [n for n in networks if n['name'] == network_name][0]
        logger.info("[neutron]: Reusing existing %s network", network)

    # find ext_net
    ext_net = [n for n in networks if n['router:external']]
    if len(ext_net) < 1:
        raise Exception("No external network found")
    ext_net = ext_net[0]

    subnets = nclient.list_subnets()['subnets']
    subnet_name = subnet['name']
    if (subnet_name not in list(map(itemgetter('name'), subnets))
            and configure_network):
        subnet = {'name': subnet['name'],
                  'network_id': network['id'],
                  # NOTE(msimonin): using the dns of chameleon
                  # for a generic openstack provider we should think to
                  # parameteried this or use public available dns
                  'cidr': subnet['cidr'],
                  'ip_version': 4}
        if dns_nameservers is not None:
            subnet.update({'dns_nameservers': dns_nameservers})
        if allocation_pool is not None:
            subnet.update({'allocation_pools': [allocation_pool]})

        s = nclient.create_subnet({'subnet': subnet})
        logger.debug(s)
        subnet = s['subnet']
        logger.info("[neutron]: %s subnet created" % subnet_name)
    else:
        subnet = [s for s in subnets if s['name'] == subnet_name][0]
        logger.info("[neutron]: Reusing %s subnet", subnet)

    # create a router
    routers = nclient.list_routers()
    router_name = ROUTER_NAME
    logger.debug(routers)
    router_present = router_name not in [r['name'] for r in routers['routers']]
    if (router_present and configure_network):
        router = {
            'name': router_name,
            'external_gateway_info': {
                'network_id': ext_net['id']
            }
        }
        r = nclient.create_router({'router': router})
        logger.info("[neutron]  %s router created" % router_name)
        # NOTE(msimonin): We should check the interface outside this block
        # in case the router is created but the interface is not added
        interface = {
            'subnet_id': subnet['id'].encode('UTF-8')
        }
        nclient.add_interface_router(str(r['router']['id']), interface)

    return (ext_net, network, subnet)


def set_free_floating_ip(env, server_id):
    nclient = neutron.Client('2', session=env['session'],
                             region_name=os.environ['OS_REGION_NAME'])
    fips = nclient.list_floatingips()['floatingips']
    fips = [fip for fip in fips if fip['fixed_ip_address'] is None]
    if len(fips) > 0:
        fip = fips.pop()
    else:
        # create from scratch
        floatingip = {'floating_network_id': env['ext_net']['id']}
        fip = nclient.create_floatingip({'floatingip': floatingip})
        fip = fip['floatingip']
    logger.info("[neutron]: Using floating ip: %s", fip)

    # Getting the port fior server_id
    ports = nclient.list_ports(device_id=server_id).get('ports')
    port_id = ports[0]['id']
    logger.info("[neutron]: Associate floating ip with the port %s" % ports)
    nclient.update_floatingip(fip['id'], {'floatingip': {'port_id': port_id}})
    return fip['floating_ip_address']


def wait_for_servers(session, servers):
    """Wait for the servers to be ready.

    Note(msimonin): we don't garantee the SSH connection to be ready.
    """
    nclient = nova.Client(NOVA_VERSION, session=session,
                          region_name=os.environ['OS_REGION_NAME'])
    while True:
        deployed = []
        undeployed = []
        for server in servers:
            c = nclient.servers.get(server.id)
            if c.addresses != {} and c.status == 'ACTIVE':
                deployed.append(server)
            if c.status == 'ERROR':
                undeployed.append(server)
        logger.info("[nova]: Polling the Deployment")
        logger.info("[nova]: %s deployed servers" % len(deployed))
        logger.info("[nova]: %s undeployed servers" % len(undeployed))
        if len(deployed) + len(undeployed) >= len(servers):
            break
        time.sleep(3)
    return deployed, undeployed


def _get_total_wanted_machines(machines):
    total = sum([machine.number for machine in machines])
    return total


def check_servers(session, machines, extra_prefix="",
                  force_deploy=False, key_name=None, image_id=None,
                  flavors='m1.medium', network=None, ext_net=None,
                  scheduler_hints=None):
    """Checks the servers status for the deployment.

    If needed, it creates new servers and add a floating ip to one of them.
    This server can be used as a gateway to the others.
    """

    scheduler_hints = scheduler_hints or []
    nclient = nova.Client(NOVA_VERSION, session=session,
                          region_name=os.environ['OS_REGION_NAME'])
    servers = nclient.servers.list(
        search_opts={'name': '-'.join([DEFAULT_PREFIX, extra_prefix])})
    wanted = _get_total_wanted_machines(machines)
    if force_deploy:
        for server in servers:
            server.delete()
        servers = []

    if len(servers) == wanted:
        logger.info("[nova]: Reusing existing servers : %s", servers)
        return servers
    elif len(servers) > 0 and len(servers) < wanted:
        raise Exception("Only %s/%s servers found" % (servers, wanted))

    # starting the servers
    total = 0
    for machine in machines:
        number = machine.number
        roles = machine.roles
        logger.info("[nova]: Starting %s servers" % number)
        logger.info("[nova]: for roles %s" % roles)
        logger.info("[nova]: with extra hints %s" % scheduler_hints)
        for _ in range(number):
            flavor = machine.flavour
            if isinstance(flavors, str):
                flavor = flavors
            else:
                flavor_to_id, _ = flavors
                flavor = flavor_to_id[flavor]

            if scheduler_hints:
                _scheduler_hints = \
                    scheduler_hints[total % len(scheduler_hints)]
            else:
                _scheduler_hints = []

            server = nclient.servers.create(
                name='-'.join([DEFAULT_PREFIX, extra_prefix, str(total)]),
                image=image_id,
                flavor=flavor,
                nics=[{'net-id': network['id']}],
                key_name=key_name,
                security_groups=[SECGROUP_NAME],
                scheduler_hints=_scheduler_hints)
            servers.append(server)
            total = total + 1
    return servers


def check_gateway(env, with_gateway, servers):
    gateway = sorted(servers, key=lambda s: s.id)[0]
    if with_gateway:
        nclient = nova.Client(NOVA_VERSION, session=env['session'],
                              region_name=os.environ['OS_REGION_NAME'])
        gateway = nclient.servers.get(gateway.id)
        gw_floating_ips = [
            n for n in gateway.addresses[env['network']['name']]
            if n['OS-EXT-IPS:type'] == 'floating'
        ]
        if len(gw_floating_ips) == 0:
            gateway_ip = set_free_floating_ip(env, gateway.id)
        else:
            gateway_ip = gw_floating_ips[0]['addr']

        logger.info("[nova]: Reusing %s as gateway with ip %s",
                    gateway,
                    gateway_ip)
    return gateway_ip, gateway


def is_in_current_deployment(server, extra_prefix=""):
    """Check if an existing server in the system take part to
    the current deployment
    """
    return re.match(r"^%s" % '-'.join([DEFAULT_PREFIX, extra_prefix]),
                    server.name) is not None


def allow_address_pairs(session, network, subnet):
    """Allow several interfaces to be added and accessed from the other machines.

    This is particularly useful when working with virtual ips.
    """
    nclient = neutron.Client('2', session=session,
                             region_name=os.environ['OS_REGION_NAME'])
    ports = nclient.list_ports()
    ports_to_update = filter(
        lambda p: p['network_id'] == network['id'],
        ports['ports'])
    logger.info('[nova]: Allowing address pairs for ports %s' %
                list(map(lambda p: p['fixed_ips'], ports_to_update)))
    for port in ports_to_update:
        try:
            nclient.update_port(port['id'], {
                'port': {
                    'allowed_address_pairs': [{
                        'ip_address': subnet
                        }]
                    }
                })
        except Exception:
            # NOTE(msimonin): dhcp and router interface port
            # seems to have enabled_sec_groups = False which
            # prevent them to be updated, just throw a warning
            # a skip them
            logger.warn("Can't update port %s" % port)


def check_environment(provider_conf):
    """Check all ressources needed by Enos."""
    session = get_session()
    image_id = check_glance(session, provider_conf.image)
    flavor_to_id, id_to_flavor = check_flavors(session)
    ext_net, network, subnet = check_network(
        session,
        provider_conf.configure_network,
        provider_conf.network,
        subnet=provider_conf.subnet,
        dns_nameservers=provider_conf.dns_nameservers,
        allocation_pool=provider_conf.allocation_pool)

    return {
        'session': session,
        'image_id': image_id,
        'flavor_to_id': flavor_to_id,
        'id_to_flavor': id_to_flavor,
        'ext_net': ext_net,
        'network': network,
        'subnet': subnet
    }


def finalize(env, provider_conf, gateway_ip, servers, keyfnc, extra_ips=None):
    def build_roles(provider_conf, env, servers, keyfnc):
        result = {}
        pools = mk_pools(servers, keyfnc)
        machines = provider_conf.machines
        for desc in machines:
            flavor = desc.flavour
            nb = desc.number
            roles = desc.roles
            nodes = pick_things(pools, flavor, nb)
            for role in roles:
                result.setdefault(role, []).extend(nodes)

        return result

    # Distribute the machines according to the resource/topology
    # specifications
    os_roles = build_roles(provider_conf, env, servers, keyfnc)

    extra = {}
    network_name = provider_conf.network['name']
    if provider_conf.gateway:
        extra.update({
            'gateway': gateway_ip,
            'gateway_user': provider_conf.gateway_user,
            'forward_agent': True
            })
    extra.update({'ansible_become': 'yes'})

    # build the enos roles
    roles = {}
    for os_role, servers in os_roles.items():
        for server in servers:
            roles.setdefault(os_role, []).append(Host(
                server.addresses[network_name][0]['addr'],
                # NOTE(msimonin): the alias is used by ansible and thus
                # must be an ascii hostname
                alias=str(server.name),
                user=provider_conf.user,
                extra=extra))

    # build the network
    extra_ips = extra_ips or []
    net = ipaddress.ip_network(env['subnet']['cidr'])
    network = {
        'cidr': env['subnet']["cidr"],
        'start': str(net[100]),
        'end': str(net[-3]),
        'extra_ips': extra_ips,
        'gateway': env['subnet']["gateway_ip"],
        'dns': '8.8.8.8',
        'roles': provider_conf.networks
    }

    return roles, [network]


class Openstack(Provider):

    def init(self, force_deploy=False):
        logger.info("Checking the existing environment")

        env = check_environment(self.provider_conf)
        servers = check_servers(
            env['session'],
            self.provider_conf.machines,
            extra_prefix=self.provider_conf.prefix,
            force_deploy=force_deploy,
            key_name=self.provider_conf.key_name,
            image_id=env['image_id'],
            flavors=(env['flavor_to_id'], env['id_to_flavor']),
            network=env['network'],
            ext_net=env['ext_net'])

        logger.info("Waiting for the all the servers to be active")
        deployed, _ = wait_for_servers(env['session'], servers)
        # NOTE(msimonin): handle the case of undeployed nodes

        deployed = sorted(deployed, key=lambda s: s.name)

        gateway_ip, _ = check_gateway(
            env,
            self.provider_conf.gateway,
            deployed)

        allow_address_pairs(env['session'],
                            env['network'],
                            self.provider_conf.subnet['cidr'])

        # NOTE(msimonin): polling is missing
        # we aren't sure that machines are ssh-reachable
        # this is delegated to a global ansible playbook
        return finalize(env,
                        self.provider_conf,
                        gateway_ip,
                        servers,
                        lambda s: env['id_to_flavor'][s.flavor['id']])

    def destroy(self):
        session = get_session()
        nclient = nova.Client(NOVA_VERSION, session=session,
                              region_name=os.environ['OS_REGION_NAME'])
        servers = nclient.servers.list()
        for server in servers:
            if is_in_current_deployment(server):
                logger.info("Deleting %s" % server)
                server.delete()
