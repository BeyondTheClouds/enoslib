from collections import defaultdict
from typing import Iterable, Optional
from enoslib.objects import Host, Network, RolesLike, Roles
import os

from enoslib.errors import EnosFilePathError


def _check_tmpdir(tmpdir):
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    else:
        if not os.path.isdir(tmpdir):
            raise EnosFilePathError("%s is not a directory" % tmpdir)
        else:
            pass


def remove_hosts(roles, hosts_to_keep):
    if roles is None:
        return None
    updated_roles = defaultdict(list)
    for role, hosts in roles.items():
        for host in hosts:
            if host.alias in hosts_to_keep:
                updated_roles[role].append(host)
    return updated_roles


def _hostslike_to_roles(input_data: Optional[RolesLike]) -> Optional[Roles]:
    if input_data is None:
        return None
    if isinstance(input_data, Roles):
        return input_data
    if isinstance(input_data, Host):
        return Roles(all=[input_data])
    if hasattr(input_data, "__iter__"):
        return Roles(all=input_data)
    error = (
        f"{type(input_data)} isn't an acceptable type for RolesLike"
        "=Union[Roles, Iterable[Host], Host]"
    )
    raise ValueError(error)


def get_address(host: Host, networks: Optional[Iterable[Network]] = None) -> str:
    """Auxiliary function to get the IP address for the Host

    Args:
        host: Host information
        networks: List of networks

    Returns:
        str: IP address from host
    """
    if networks is None:
        return host.address

    address = host.filter_addresses(networks, include_unknown=False)

    if not address or not address[0].ip:
        raise ValueError(f"IP address not found. Host: {host}, Networks: {networks}")

    if len(address) > 1:
        raise ValueError(
            f"Cannot determine single IP address."
            f"Options: {address} Host: {host}, Networks: {networks}"
        )
    return str(address[0].ip.ip)
