# -*- coding: utf-8 -*-
import logging
import pathlib
from typing import List, Optional

import iotlabcli.auth

from enoslib.api import play_on
from enoslib.objects import Host
from enoslib.infra.provider import Provider
from enoslib.infra.enos_iotlab.iotlab_api import IotlabAPI
from enoslib.infra.enos_iotlab.objects import IotlabHost, IotlabSensor, IotlabNetwork
from enoslib.infra.utils import mk_pools, pick_things

from enoslib.infra.enos_iotlab.constants import PROD
from enoslib.infra.enos_iotlab.configuration import (
    PhysNodeConfiguration,
)

logger = logging.getLogger(__name__)


class Iotlab(Provider):
    """
    The provider to be used when deploying on FIT/IoT-LAB testbed

    Args:
        provider_conf (iotlab.Configuration): Configuration file for IoT-LAB platform
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider_conf = self.provider_conf.finalize()
        self.client = IotlabAPI()
        self.hosts: List[IotlabHost] = []
        self.sensors: List[IotlabSensor] = []
        self.networks: List[IotlabNetwork] = []

    def init(self, force_deploy: bool = False):
        """
        Take ownership over FIT/IoT-LAB resources

        Check if job is already running in the testbed
        (based on the name given on config).
        Submit a new job if necessary and wait its initialization.
        Return inventory of resources allocated.

        Returns:
            (roles, dict): representing the inventory of resources.

        """
        self._profiles()
        self._reserve()
        self._deploy()

        return self._to_enoslib()

    def collect_data_experiment(self, exp_dir: Optional[str] = None):
        """
        Collects data about experiment from frontends

        During the experiment, FIT/IoT-LAB collects and saves a lot of data
        about it under the folder ~/.iot-lab/.
        This method will connect to each frontend used during the test
        (grenoble, paris, etc), will compress and fetch this data.

        2 kinds of information are collected:
        1. REST API, about experiment: saved as <exp_id>.tar.gz

        2. .iot-lab/, from each frontend: saved as <exp_id>-<frontend>.tar.gz
        Args:
            exp_dir: Where to saves the tar.gz files. If none is provided
            it will save in the current folder.
        """
        if exp_dir is None:
            dest_dir = str(pathlib.Path.cwd())
        else:
            dest_dir = str(pathlib.Path(exp_dir))

        self.client.collect_data_experiment(dest_dir)
        exp_id = self.client.get_job_id()
        # getting sites used in tests
        sites = set()
        for sensor in self.sensors:
            sites.add(sensor.site)
        for host in self.hosts:
            sites.add(host.site)

        user, _ = iotlabcli.auth.get_user_credentials()
        roles = {
            "frontend": [Host(site + ".iot-lab.info", user=user) for site in sites]
        }
        logger.info(
            "Collecting experiment data from sites. Saving in folder: %s", dest_dir
        )
        with play_on(roles=roles, on_error_continue=True) as p:
            filename = "%d-{{ inventory_hostname }}.tar.gz" % (exp_id)
            # use --ignore-command-error to avoid errors if monitoring
            # files are being written
            p.shell("cd .iot-lab/; tar --ignore-command-error -czf %s %d/"
                    % (filename, exp_id))
            p.fetch(src=".iot-lab/" + filename, dest=dest_dir + "/", flat=True)
            p.shell("cd .iot-lab/; rm -f %s" % filename)

    def destroy(self):
        """Destroys the job and monitoring profiles"""
        self.client.stop_experiment()
        self.client.del_profile()

    def _assert_clear_pool(self, pool_nodes):
        """Auxialiry method to verify that all nodes from the pool were used"""
        for nodes in pool_nodes.values():
            assert len(nodes) == 0

    def _populate_from_board_nodes(self, iotlab_nodes: list):
        """Populate self.host from board nodes"""
        pool_nodes = mk_pools(iotlab_nodes, lambda n: (n['site'], n['archi']))
        for config in self.provider_conf.machines:
            iot_nodes = pick_things(
                pool_nodes, (config.site, config.archi), config.number)
            for node in iot_nodes:
                if node['network_address'].startswith('a8'):
                    iotlab_host = IotlabHost(
                        address=node['network_address'], roles=config.roles,
                        site=node['site'], uid=node['uid'], archi=node['archi'])
                    self.hosts.append(iotlab_host)
                else:
                    iotlab_sensor = IotlabSensor(
                        address=node['network_address'], roles=config.roles,
                        site=node['site'], uid=node['uid'], archi=node['archi'],
                        image=config.image, iotlab_client=self.client)
                    self.sensors.append(iotlab_sensor)

        self._assert_clear_pool(pool_nodes)

    def _populate_from_phys_nodes(self, iotlab_nodes: list):
        """Populate self.host from physical nodes"""
        pool_nodes = mk_pools(iotlab_nodes, lambda n: n['network_address'])
        for config in self.provider_conf.machines:
            for s in config.hostname:
                # only 1 is available selecting by hostname
                iot_node = pick_things(pool_nodes, s, 1)[0]
                if iot_node['network_address'].startswith('a8'):
                    iotlab_host = IotlabHost(
                        address=iot_node['network_address'], roles=config.roles,
                        site=iot_node['site'], uid=iot_node['uid'],
                        archi=iot_node['archi'])
                    self.hosts.append(iotlab_host)
                else:
                    iotlab_sensor = IotlabSensor(
                        address=iot_node['network_address'],
                        roles=config.roles, site=iot_node['site'],
                        uid=iot_node['uid'], archi=iot_node['archi'],
                        image=config.image, iotlab_client=self.client)
                    self.sensors.append(iotlab_sensor)

        self._assert_clear_pool(pool_nodes)

    def _deploy(self):
        """
        Deploy image on nodes as described in given configuration

        Wait for A8 nodes to boot
        """
        image_dict = {}
        for sensor in self.sensors:
            if sensor.image is not None:
                image_dict.setdefault(sensor.image, []).append(sensor.address)
        for image, sensors in image_dict.items():
            self.client.flash_nodes(image, sensors)

        self.client.wait_a8_nodes([h.ssh_address for h in self.hosts])

    def _reserve(self):
        """Reserve resources on platform"""
        iotlab_nodes = self.client.get_resources(
            self.provider_conf.job_name, self.provider_conf.walltime,
            self.provider_conf.machines)

        if isinstance(self.provider_conf.machines[0], PhysNodeConfiguration):
            self._populate_from_phys_nodes(iotlab_nodes)
        else:
            self._populate_from_board_nodes(iotlab_nodes)

        self._get_networks()

        logger.info("Finished reserving nodes: hosts %s, sensors %s",
            str(self.hosts), str(self.sensors))

    def _get_networks(self):
        """
        Get networks used by A8 nodes on platform

        By now use a fixed list of addresses since the API
        doesn't provide any information about networks in testbed.
        """
        networks_info = {
            "grenoble": [
                "10.0.12.0/21",
                "2001:660:5307:3000::/64",
            ],
            "paris": [
                "10.0.68.0/21",
                "2001:660:330f:a200::/64",
            ],
            "saclay": [
                "10.0.44.0/21",
                "2001:660:3207:400::/64",
            ],
            "strasbourg": [
                "10.0.36.0/21",
                "2001:660:4701:f080::/64",
            ],
            "lyon": [
                "10.0.100.0/21",
            ],
        }
        sites = set()
        for host in self.hosts:
            sites.add(host.site)

        # add networks from user
        for net in self.provider_conf.networks:
            self.networks.extend([
                IotlabNetwork(roles=net.roles, address=addr)
                for addr in networks_info.get(net.site.lower(), [])
            ])
            sites.discard(net.site.lower())

        # add default networks not in conf
        for site in sites:
            self.networks.extend([
                IotlabNetwork(roles=[PROD], address=addr)
                for addr in networks_info.get(site.lower(), [])
            ])

    def _profiles(self):
        """Create profiles"""
        if self.provider_conf.profiles is None:
            return

        for profile in self.provider_conf.profiles:
            if profile.radio is None and profile.consumption is None:
                continue

            self.client.create_profile(
                name=profile.name, archi=profile.archi,
                radio=profile.radio, consumption=profile.consumption,
            )

    def _to_enoslib(self):
        """Transform from provider specific resources to library-level resources"""
        roles = {}
        for host in self.hosts:
            for role in host.roles:
                if host.ssh_address:
                    roles.setdefault(role, []).append(
                        Host(host.ssh_address, user="root")
                    )
                    # shouldn't I be able to pass only host?
                    # Not because ansible inventory is based on address and
                    # our ssh_address is other for A8 nodes..
        for sensor in self.sensors:
            for role in sensor.roles:
                roles.setdefault(role, []).append(sensor)

        networks = {}
        for network in self.networks:
            for role in network.roles:
                networks.setdefault(role, []).append(network)

        return roles, networks