import contextlib
import logging
import time
from typing import Any, Generator, List, Optional

import chi
from chi import container

from enoslib.infra.enos_openstack import utils

from .constants import CONTAINER_LABELS, ROLES, ROLES_SEPARATOR

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(rc_file: str) -> Generator[str, None, None]:
    with utils.source_credentials_from_rc_file(rc_file) as site:
        chi.context.reset()
        chi.use_site(site)
        yield site


def check_connection_to_api(rc_file: str) -> str:
    with source_credentials_from_rc_file(rc_file) as _site:
        try:
            chi.blazar().lease.list()
            return f"Successfully connected to {_site}!"
        except Exception as err:
            raise Exception(f"Failed to connect to {_site}!") from err


def get_node_address(node) -> List:
    addrs = []
    if hasattr(node, "addresses"):
        addresses = getattr(node, "addresses")
        for _, v in addresses.items():
            for ip in v:
                addrs.append(ip["addr"])
    return addrs


def get_node_uuid(node) -> Optional[Any]:
    uuid = None
    if hasattr(node, "uuid"):
        uuid = getattr(node, "uuid")
    return uuid


def get_node_roles(node) -> Optional[List[str]]:
    roles = None
    if hasattr(node, CONTAINER_LABELS):
        container_roles = getattr(node, CONTAINER_LABELS)
        roles = container_roles[ROLES].split(ROLES_SEPARATOR)
    return roles


def wait_for_addresses(container_ref: str):
    while True:
        logger.info("Waiting for IP address: container(%s)...", container_ref)
        _container = container.get_container(container_ref)
        addrs = get_node_address(_container)
        if addrs:
            logger.info("Container(%s) IP address: %s", container_ref, addrs)
            return _container
        time.sleep(5)
