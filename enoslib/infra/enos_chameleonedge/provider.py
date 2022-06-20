import os
import logging
from typing import List, Tuple
from .constants import (
    ROLES,
    ROLES_SEPARATOR,
    CONTAINER_LABELS
)
from enoslib.infra.enos_chameleonedge.chi_api_utils import (
    check_connection_to_api
)
from enoslib.infra.enos_chameleonedge.objects import ChameleonDevice, ChameleonNetwork
from enoslib.objects import Networks, Roles
from enoslib.infra.enos_chameleonedge.chameleon_api import ChameleonAPI
from enoslib.infra.provider import Provider

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

    def init(self, force_deploy=False):
        """
        Take ownership over CHI@Edge resources
        Return inventory of resources allocated.

        Returns:
            (roles, dict): representing the inventory of resources.
        """
        leased_resources = self._reserve()
        self._deploy(leased_resources)

        return self._to_enoslib()

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
            for role in device.roles:
                roles.setdefault(role, []).append(device)

        networks = Networks()
        for network in self.networks:
            for role in network.roles:
                networks.setdefault(role, []).append(network)

        return roles, networks

    @staticmethod
    def from_api_resources_to_enoslib_chameleon_device(concrete_resources, rc_file):
        devices = []
        for node in concrete_resources:
            devices.append(
                ChameleonDevice(
                    address=ChameleonEdge.get_node_address(node)[0],
                    roles=ChameleonEdge.get_node_roles(node),
                    uuid=ChameleonEdge.get_node_uuid(node),
                    rc_file=rc_file,
                )
            )
        return devices

    @staticmethod
    def get_node_address(node):
        addrs = []
        if hasattr(node, "addresses"):
            addresses = getattr(node, "addresses")
            for (
                k,
                v,
            ) in addresses.items():
                for ip in v:
                    addrs.append(ip["addr"])
        return addrs

    @staticmethod
    def get_node_uuid(node):
        uuid = None
        if hasattr(node, "uuid"):
            uuid = getattr(node, "uuid")
        return uuid

    @staticmethod
    def get_node_roles(node):
        roles = None
        if hasattr(node, CONTAINER_LABELS):
            container_roles = getattr(node, CONTAINER_LABELS)
            roles = container_roles[ROLES].split(ROLES_SEPARATOR)
        return roles

    def destroy(self):
        """Release testbed resources."""
        self.client.release_resources(
            self.provider_conf.lease_name,
            self.provider_conf.rc_file,
        )

    def test_slot(self, start_time: int) -> bool:
        """Test if it is possible to reserve the configuration corresponding
        to this provider at start_time"""
        # Unimplemented
        return False


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
