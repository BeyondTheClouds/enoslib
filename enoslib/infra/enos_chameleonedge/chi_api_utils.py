import contextlib
import logging
import time
import chi
from chi import container
from .constants import (
    ROLES,
    ROLES_SEPARATOR,
    CONTAINER_LABELS,
)
from enoslib.infra.enos_openstack import utils

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(rc_file):
    with utils.source_credentials_from_rc_file(rc_file) as site:
        chi.context.reset()
        chi.use_site(site)
        yield site


def check_connection_to_api(rc_file: str):
    with source_credentials_from_rc_file(rc_file) as _site:
        try:
            chi.blazar().lease.list()
            return f"Successfully connected to {_site}!"
        except Exception:
            raise Exception(f"Failed to connect to {_site}!")


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


def get_node_uuid(node):
    uuid = None
    if hasattr(node, "uuid"):
        uuid = getattr(node, "uuid")
    return uuid


def get_node_roles(node):
    roles = None
    if hasattr(node, CONTAINER_LABELS):
        container_roles = getattr(node, CONTAINER_LABELS)
        roles = container_roles[ROLES].split(ROLES_SEPARATOR)
    return roles


def wait_for_addresses(container_ref):
    while True:
        logger.info(f"Waiting for IP address: container({container_ref})...")
        _container = container.get_container(container_ref)
        addrs = get_node_address(_container)
        if addrs:
            logger.info(f"Container({container_ref}) IP address: {addrs}")
            return container
        time.sleep(5)
