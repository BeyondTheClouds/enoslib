import os
from collections import defaultdict
from ipaddress import IPv6Interface
from typing import Dict, Iterable, Mapping, Optional

from enoslib.errors import EnosFilePathError
from enoslib.objects import Host, Network, Roles, RolesLike


def _check_tmpdir(tmpdir):
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    else:
        if not os.path.isdir(tmpdir):
            raise EnosFilePathError(f"{tmpdir} is not a directory")
        else:
            pass


def remove_hosts(roles: Mapping, hosts_to_keep: Iterable) -> Optional[Dict]:
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

    addresses = host.filter_addresses(networks, include_unknown=False)

    # Filter out empty addresses and get IPs
    ips = [addr.ip for addr in addresses if addr.ip is not None]

    if len(ips) == 0:
        raise ValueError(f"IP address not found. Host: {host}, Networks: {networks}")

    # For IPv6, we may have multiple IPv6 addresses.  Select the one with
    # the largest prefix size (e.g. /128 instead of /64)
    # See https://gitlab.inria.fr/discovery/enoslib/-/issues/183
    if all([isinstance(ip, IPv6Interface) for ip in ips]):
        ips = sorted(ips, key=lambda ip: ip.network.prefixlen)[-1:]

    if len(ips) > 1:
        raise ValueError(
            f"Cannot determine single IP address. "
            f"Options: {addresses} Host: {host}, Networks: {networks}"
        )
    return str(ips[0].ip)
