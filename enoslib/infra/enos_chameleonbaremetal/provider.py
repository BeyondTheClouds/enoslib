# -*- coding: utf-8 -*-

from blazarclient import client as blazar_client
from neutronclient.neutron import client as neutron
from itertools import groupby

import enoslib.infra.enos_chameleonkvm.provider as cc
import enoslib.infra.enos_openstack.provider as openstack
import datetime
import logging
import os
import time

logger = logging.getLogger(__name__)

LEASE_NAME = "enos-lease"
PORT_NAME = "enos-port"


def lease_is_reusable(lease):
    return lease['action'] == 'START' or lease['action'] == 'CREATE'


def lease_is_running(lease):
    return lease['action'] == 'START' and lease['status'] == 'COMPLETE'


def lease_is_terminated(lease):
    return lease['action'] == 'STOP'


def lease_to_s(lease):
    return "[id=%s, name=%s, start=%s, end=%s, action=%s, status=%s]" % (
        lease['id'],
        lease['name'],
        lease['start_date'],
        lease['end_date'],
        lease['action'],
        lease['status'])


def create_blazar_client(config, session):
    """Check the reservation, creates a new one if nescessary."""
    return blazar_client.Client(session=session,
                                service_type="reservation",
                                region_name=os.environ["OS_REGION_NAME"])


def get_reservation(bclient, provider_conf):
    leases = bclient.lease.list()
    leases = [l for l in leases if l["name"] == provider_conf['lease_name']]
    if len(leases) >= 1:
        lease = leases[0]
        if lease_is_reusable(lease):
            logger.info("Reusing lease %s" % lease_to_s(lease))
            return lease
        elif lease_is_terminated(lease):
            logger.warning("%s is terminated, destroy it" % lease_to_s(lease))
            return lease
        else:
            logger.error("Error with %s" % lease_to_s(lease))
            raise Exception("lease_error")
    else:
        return None


def by_flavor(x):
    return x['flavor']


def create_reservation(bclient, provider_config):
    # NOTE(msimonin): This implies that
    #  * UTC is used
    #  * we don't support yet in advance reservation
    resources = provider_config['resources']
    start_datetime = datetime.datetime.utcnow()
    w = provider_config['walltime'].split(':')
    delta = datetime.timedelta(hours=int(w[0]),
                               minutes=int(w[1]),
                               seconds=int(w[2]))
    # Make sure we're not reserving in the past by adding 1 minute
    # This should be rare
    start_datetime = start_datetime + datetime.timedelta(minutes=1)
    end_datetime = start_datetime + delta
    start_date = start_datetime.strftime('%Y-%m-%d %H:%M')
    end_date = end_datetime.strftime('%Y-%m-%d %H:%M')
    logger.info("[blazar]: Claiming a lease start_date=%s, end_date=%s",
                 start_date,
                 end_date)

    reservations = []
    for flavor, descs in groupby(resources['machines'], key=by_flavor):
        # NOTE(msimonin): We create one reservation per flavor
        total = sum([desc['number'] for desc in descs])
        resource_properties = "[\"=\", \"$node_type\", \"%s\"]" % flavor

        reservations.append({
            'min': total,
            'max': total,
            'resource_properties': resource_properties,
            'hypervisor_properties': '',
            'resource_type': 'physical:host'
            })

    lease = bclient.lease.create(
        provider_config['lease_name'],
        start_date,
        end_date,
        reservations,
        [])
    return lease


def wait_reservation(bclient, lease):
    logger.info("[blazar]: Waiting for %s to start" % lease_to_s(lease))
    lease = bclient.lease.get(lease['id'])
    while(not lease_is_running(lease)):
        time.sleep(10)
        lease = bclient.lease.get(lease['id'])
        logger.info("[blazar]: Waiting for %s to start" % lease_to_s(lease))
    return lease


def check_reservation(config, session):
    bclient = create_blazar_client(config, session)
    lease = get_reservation(bclient, config)
    if lease is None:
        lease = create_reservation(bclient, config)
    wait_reservation(bclient, lease)
    logger.info("[blazar]: Using %s" % lease_to_s(lease))
    logger.debug(lease)
    return lease


def check_extra_ports(session, network, total):
    nclient = neutron.Client('2', session=session,
                             region_name=os.environ['OS_REGION_NAME'])
    ports = nclient.list_ports()['ports']
    logger.debug("Found %s ports" % ports)
    port_name = PORT_NAME
    ports_with_name = list(filter(lambda p: p['name'] == port_name, ports))
    logger.info("[neutron]: Reusing %s ports" % len(ports_with_name))
    # create missing ports
    for _ in range(0, total - len(ports_with_name)):
        port = {'admin_state_up': True,
                'name': PORT_NAME,
                'network_id': network['id']}
        # Checking port with PORT_NAME
        nclient.create_port({'port': port})
    ports = nclient.list_ports()['ports']
    ports_with_name = list(filter(lambda p: p['name'] == port_name, ports))
    ip_addresses = []
    for port in ports_with_name:
        ip_addresses.append(port['fixed_ips'][0]['ip_address'])
    logger.info("[neutron]: Returning %s free ip addresses" % ip_addresses)
    return ip_addresses


class Chameleonbaremetal(cc.Chameleonkvm):

    def init(self, force_deploy=False):

        conf = self.provider_conf
        env = openstack.check_environment(conf)
        lease = check_reservation(conf, env['session'])
        extra_ips = check_extra_ports(env['session'],
                                      env['network'],
                                      conf['extra_ips'])
        reservations = lease['reservations']
        machines = self.provider_conf["resources"]["machines"]
        machines = sorted(machines, key=by_flavor)
        servers = []
        for flavor, descs in groupby(machines, key=by_flavor):
            machines = list(descs)
            # NOTE(msimonin): There should be only one reservation per flavor
            hints = [{'reservation': r['id']} for r in reservations
                             if flavor in r['resource_properties']]
            os_servers = openstack.check_servers(
                env['session'],
                {"machines": machines},
                extra_prefix="{}__{}__".format(conf['prefix'], flavor),
                force_deploy=force_deploy,
                key_name=conf.get('key_name'),
                image_id=env['image_id'],
                flavors="baremetal",
                network=env['network'],
                ext_net=env['ext_net'],
                scheduler_hints=hints)
            servers.extend(os_servers)

        deployed, _ = openstack.wait_for_servers(
            env['session'],
            servers)

        gateway_ip, _ = openstack.check_gateway(
            env,
            conf.get('gateway', False),
            deployed)

        # NOTE(msimonin) build the roles and networks This is a bit tricky here
        # since flavor (e.g compute_haswell) doesn't correspond to a flavor
        # attribute of the nova server object. We have to encode the flavor
        # name (e.g compute_haswell) in the server name. Decoding the flavor
        # name from the server name helps then to form the roles.
        return openstack.finalize(
            env,
            conf,
            gateway_ip,
            deployed,
            lambda s: s.name.split('__')[1],
            extra_ips=extra_ips)

    def destroy(self):
        # destroy the associated lease should be enough
        session = openstack.get_session()
        bclient = create_blazar_client(self.provider_conf, session)
        lease = get_reservation(bclient, self.provider_conf)
        bclient.lease.delete(lease['id'])
        logger.info("Destroyed %s" % lease_to_s(lease))

    def default_config(self):
        default_config = super(Chameleonbaremetal, self).default_config()
        default_config.update({
            'type': 'chameleonbaremetal',
            # Name os the lease to use
            'lease_name': 'enos-lease',
            # Glance image to use
            'image_name': 'CC-Ubuntu16.04',
            # User to use to connect to the machines
            # (sudo will be used to configure them)
            'user': 'cc',
            # True iff Enos must configure a network stack for you
            'configure_network': False,
            # Name of the network to use or to create
            'network': {'name': 'sharednet1'},
            # Name of the subnet to use or to create
            'subnet': {'name': 'sharednet1-subnet'},
            # DNS server to use when creating network
            'dns_nameservers': ['130.202.101.6', '130.202.101.37'],
            # Experiment duration
            "walltime": "02:00:00",
            # extra ips to reserve
            "extra_ips": 0
        })

        return default_config
