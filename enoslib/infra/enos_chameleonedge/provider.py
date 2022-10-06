import os
import logging
from typing import List, Tuple
from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice, ChameleonNetwork
from enoslib.objects import Networks, Roles
from enoslib.infra.enos_chameleonedge.chameleon_api import ChameleonAPI
from enoslib.infra.provider import Provider
from .chi_api_utils import (
    get_node_address,
    get_node_roles,
    get_node_uuid,
    check_connection_to_api,
)

logger = logging.getLogger(__name__)


class ChameleonEdge(Provider):
    """
    The provider to be used when deploying on CHI@Edge testbed

    Args:
        provider_conf: Configuration file for Chameleon platform
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider_conf = self.provider_conf.finalize()
        self.client = ChameleonAPI()
        self.devices: List[ChameleonDevice] = []
        self.networks: List[ChameleonNetwork] = []

    def init(self, force_deploy=False, **kwargs):
        """
        Take ownership over CHI@Edge resources
        Return inventory of resources allocated.

        Returns:
            (roles, dict): representing the inventory of resources.
        """
        leased_resources = self._reserve()
        self._deploy(leased_resources)

        return self._to_enoslib()

    def set_reservation(self, timestamp: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )

    def _reserve(self):
        """Reserve resources on platform"""
        return self.client.get_resources(
            self.provider_conf.lease_name,
            self.provider_conf.walltime,
            self.provider_conf.rc_file,
            self.provider_conf.machines,
        )

    def _deploy(self, leased_resources):
        """
        Deploy container on devices.
        """
        concrete_resources = self.client.deploy_containers(
            self.provider_conf.rc_file, self.provider_conf.machines, leased_resources
        )
        self.devices = self.from_api_resources_to_enoslib_chameleon_device(
            concrete_resources, self.provider_conf.rc_file
        )

        logger.info("Deployment finished: %s", str(self.devices))

    def _to_enoslib(self):
        """Transform from provider specific resources to library-level resources"""
        roles = Roles()
        for device in self.devices:
            roles.add_one(device, device.roles)

        networks = Networks()
        for network in self.networks:
            networks.add_one(network, network.roles)

        return roles, networks

    def from_api_resources_to_enoslib_chameleon_device(
        self, concrete_resources, rc_file
    ):
        devices = []
        for node in concrete_resources:
            node = self.client.get_container(node.uuid)
            devices.append(
                ChameleonDevice(
                    address=get_node_address(node)[0],
                    roles=get_node_roles(node),
                    uuid=get_node_uuid(node),
                    rc_file=rc_file,
                )
            )
        return devices

    def destroy(self, wait=False):
        """Release testbed resources."""
        self.client.release_resources(
            self.provider_conf.lease_name,
            self.provider_conf.rc_file,
        )

    def offset_walltime(self, offset: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )


def check() -> List[Tuple[str, bool, str]]:
    openrc_files = []
    for file in os.listdir("./"):
        if file.endswith(".sh") and is_chameleon_openrc_file(file):
            openrc_files.append(file)

    statuses = []
    for openrc in openrc_files:
        try:
            check_result = check_connection_to_api(openrc)
            statuses.append(("api:access", True, check_result))
        except Exception as e:
            statuses.append(("api:access", False, str(e)))

    if not statuses:
        statuses.append(
            ("api:access", False, f"No openrc files found at: {os.getcwd()}")
        )
    return statuses


def is_chameleon_openrc_file(_file):
    with open(_file) as file:
        lines = file.readlines()
        for line in lines:
            if "export OS_AUTH_TYPE" in line:
                return True
    return False
