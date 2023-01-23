import datetime
import logging
import os
import time
from itertools import groupby
from typing import Dict, List, Mapping, Optional

from blazarclient import client as blazar_client
from keystoneauth1.session import Session
from neutronclient.neutron import client as neutron

import enoslib.infra.enos_chameleonkvm.provider as cc
import enoslib.infra.enos_openstack.provider as openstack
from enoslib.infra.enos_chameleonbaremetal.configuration import (
    Configuration,
    MachineConfiguration,
)
from enoslib.infra.enos_openstack.utils import source_credentials_from_rc_file

logger = logging.getLogger(__name__)

LEASE_NAME = "enos-lease"
PORT_NAME = "enos-port"


def lease_is_reusable(lease: Mapping) -> bool:
    statuses = ["CREATING", "STARTING, UPDATING", "ACTIVE", "PENDING"]
    return lease["status"] in statuses


def lease_is_running(lease: Mapping) -> bool:
    statuses = ["ACTIVE"]
    return lease["status"] in statuses


def lease_is_terminated(lease: Mapping) -> bool:
    statuses = ["TERMINATED"]
    return lease["status"] in statuses


def lease_to_s(lease: Mapping) -> str:
    return f'[id={lease["id"]}, name={lease["name"]}, start={lease["start_date"]}, end={lease["end_date"]}, status={lease["status"]}]'  # noqa


def create_blazar_client(
    config: Optional[Configuration], session: Session
) -> blazar_client.Client:
    """Check the reservation, creates a new one if necessary.
    config parameter is unused. We kept for compatibility.
    """
    return blazar_client.Client(
        session=session,
        service_type="reservation",
        region_name=os.environ["OS_REGION_NAME"],
    )


def get_reservation(
    bclient: blazar_client.Client, provider_conf: Configuration
) -> Optional[Dict]:
    leases = bclient.lease.list()
    leases = [lease for lease in leases if lease["name"] == provider_conf.lease_name]
    if len(leases) >= 1:
        lease = leases[0]
        if lease_is_reusable(lease):
            logger.info("Reusing lease %s", lease_to_s(lease))
            return lease
        elif lease_is_terminated(lease):
            logger.warning("%s is terminated, destroy it", lease_to_s(lease))
            return lease
        else:
            logger.error("Error with %s", lease_to_s(lease))
            raise Exception("lease_error")
    else:
        return None


def by_flavor(machine: MachineConfiguration):
    return machine.flavour


def create_reservation(
    bclient: blazar_client.Client, provider_config: Configuration
) -> Dict:
    # NOTE(msimonin): This implies that
    #  * UTC is used
    #  * we don"t support yet in advance reservation
    start_datetime = datetime.datetime.utcnow()
    w = provider_config.walltime.split(":")
    delta = datetime.timedelta(hours=int(w[0]), minutes=int(w[1]), seconds=int(w[2]))
    # Make sure we"re not reserving in the past by adding 1 minute
    # This should be rare
    start_datetime = start_datetime + datetime.timedelta(minutes=1)
    end_datetime = start_datetime + delta
    start_date = start_datetime.strftime("%Y-%m-%d %H:%M")
    end_date = end_datetime.strftime("%Y-%m-%d %H:%M")
    logger.info(
        "[blazar]: Claiming a lease start_date=%s, end_date=%s", start_date, end_date
    )

    reservations = []
    for flavor, machines in groupby(provider_config.machines, key=by_flavor):
        # NOTE(msimonin): We create one reservation per flavor
        total = sum(machine.number for machine in machines)
        resource_properties = f'["=", "$node_type", "{flavor}"]'

        reservations.append(
            {
                "min": total,
                "max": total,
                "resource_properties": resource_properties,
                "hypervisor_properties": "",
                "resource_type": "physical:host",
            }
        )

    lease = bclient.lease.create(
        provider_config.lease_name, start_date, end_date, reservations, []
    )
    return lease


def wait_reservation(bclient: blazar_client.Client, lease: Mapping) -> Dict:
    logger.info("[blazar]: Waiting for %s to start", lease_to_s(lease))
    lease_retrieved: Dict = bclient.lease.get(lease["id"])
    while not lease_is_running(lease_retrieved):
        time.sleep(10)
        lease_retrieved = bclient.lease.get(lease_retrieved["id"])
        logger.info("[blazar]: Waiting for %s to start", lease_to_s(lease_retrieved))
    return lease_retrieved


def check_reservation(config: Configuration, session: Session) -> Dict:
    bclient = create_blazar_client(config, session)
    lease = get_reservation(bclient, config)
    if lease is None:
        lease = create_reservation(bclient, config)
    wait_reservation(bclient, lease)
    logger.info("[blazar]: Using %s", lease_to_s(lease))
    logger.debug(lease)
    return lease


def check_extra_ports(session: Session, network: Mapping, total: int) -> List:
    nclient = neutron.Client(
        "2", session=session, region_name=os.environ["OS_REGION_NAME"]
    )
    ports = nclient.list_ports()["ports"]
    logger.debug("Found %s ports", ports)
    port_name = PORT_NAME
    ports_with_name = list(filter(lambda p: p["name"] == port_name, ports))
    logger.info("[neutron]: Reusing %d ports", len(ports_with_name))
    # create missing ports
    for _ in range(0, total - len(ports_with_name)):
        port = {"admin_state_up": True, "name": PORT_NAME, "network_id": network["id"]}
        # Checking port with PORT_NAME
        nclient.create_port({"port": port})
    ports = nclient.list_ports()["ports"]
    ports_with_name = list(filter(lambda p: p["name"] == port_name, ports))
    ip_addresses = []
    for port in ports_with_name:
        ip_addresses.append(port["fixed_ips"][0]["ip_address"])
    logger.info("[neutron]: Returning %s free ip addresses", ip_addresses)
    return ip_addresses


class Chameleonbaremetal(cc.Chameleonkvm):
    def init(
        self, force_deploy: bool = False, start_time: Optional[int] = None, **kwargs
    ):
        with source_credentials_from_rc_file(self.provider_conf.rc_file) as _site:
            logger.info(" Using %s.", _site)
            conf = self.provider_conf
            env = openstack.check_environment(conf)
            lease = check_reservation(conf, env["session"])
            extra_ips = check_extra_ports(
                env["session"], env["network"], conf.extra_ips
            )
            reservations = lease["reservations"]
            machines = self.provider_conf.machines
            machines = sorted(machines, key=by_flavor)
            servers = []
            for flavor, descs in groupby(machines, key=by_flavor):
                _machines = list(descs)
                # NOTE(msimonin): There should be only one reservation per flavor
                hints = [
                    {"reservation": r["id"]}
                    for r in reservations
                    if flavor in r["resource_properties"]
                ]
                # It's still a bit tricky here
                os_servers = openstack.check_servers(
                    env["session"],
                    _machines,
                    # NOTE(msimonin): we should be able to deduce the flavour from
                    # the name
                    extra_prefix=f'-o-{flavor.replace("_", "-")}-o-',
                    force_deploy=force_deploy,
                    key_name=conf.key_name,
                    image_id=env["image_id"],
                    flavors="baremetal",
                    network=env["network"],
                    ext_net=env["ext_net"],
                    scheduler_hints=hints,
                )
                servers.extend(os_servers)

            deployed, _ = openstack.wait_for_servers(env["session"], servers)

            gateway_ip, _ = openstack.check_gateway(env, conf.gateway, deployed)

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
            lambda s: s.name.split("-o-")[1].replace("-", "_"),
            extra_ips=extra_ips,
        )

    def destroy(self, wait: bool = False, **kwargs):
        with source_credentials_from_rc_file(self.provider_conf.rc_file) as _site:
            logger.info(" Using %s.", _site)
            # destroy the associated lease should be enough
            session = openstack.get_session()
            bclient = create_blazar_client(self.provider_conf, session)
            lease = get_reservation(bclient, self.provider_conf)
            if lease is None:
                logger.info("No lease to destroy")
                return
            bclient.lease.delete(lease["id"])
            logger.info("Destroyed %s", lease_to_s(lease))

    def set_reservation(self, timestamp: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )

    def offset_walltime(self, offset: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )
