import os
from collections import defaultdict
from ipaddress import IPv6Interface
from typing import Dict, Iterable, Mapping, Optional, Tuple

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


# Implementation note: we can't simply use "ssh -J gwA,gwB" because we
# need to disable StrictHostKeyChecking at each hop.
def generate_ssh_option_gateway(gateways: Iterable[Tuple[str, Optional[str]]]) -> str:
    """Generates the appropriate SSH options to connect through a list of
    gateways (i.e. SSH jump hosts).

    The first gateway in the argument should be the outermost one.  For
    example, the connection [client] -> [gwA] -> [gwB] -> [destination]
    can be expressed as [('gwA', None), ('gwB', None)]

    Args:
        gateways: List of (gateway, gateway_user) tuples

    Returns:
        str: ssh option that can be fed to the "ssh" command
    """
    # Filter out items with a gateway set to None or to an empty string.
    gateways = [gw for gw in gateways if gw[0] is not None and gw[0] != ""]
    # No more than 2 hops for now (it's complex enough to handle two)
    # To do more, we will likely need to work recursively.
    if len(gateways) > 2:
        raise ValueError("Only two SSH gateways are supported at the moment")
    if len(gateways) == 0:
        return ""
    # Disable hostkey checking for all hops
    common_args = [
        "-o StrictHostKeyChecking=no",
        "-o UserKnownHostsFile=/dev/null",
    ]
    inner_gateway = gateways[-1][0]
    inner_gateway_user = gateways[-1][1]
    inner_proxy_cmd = ["ssh -W %h:%p"]
    inner_proxy_cmd.extend(common_args)
    if inner_gateway_user is not None and inner_gateway_user != "":
        inner_proxy_cmd.append(f"-l {inner_gateway_user}")
    if len(gateways) == 1:
        inner_proxy_cmd.append(inner_gateway)
        final_proxy_cmd = " ".join(inner_proxy_cmd)
        return f'-o ProxyCommand="{final_proxy_cmd}"'
    if len(gateways) == 2:
        outer_gateway = gateways[0][0]
        outer_gateway_user = gateways[0][1]
        # Escape tokens so they are interpreted in the second SSH command
        outer_proxy_cmd = ["ssh -W %%h:%%p"]
        outer_proxy_cmd.extend(common_args)
        if outer_gateway_user is not None and outer_gateway_user != "":
            outer_proxy_cmd.append(f"-l {outer_gateway_user}")
        outer_proxy_cmd.append(outer_gateway)
        final_outer_proxy_cmd = " ".join(outer_proxy_cmd)
        # Integrate in first command
        inner_proxy_cmd.append(f"-o ProxyCommand='{final_outer_proxy_cmd}'")
        inner_proxy_cmd.append(inner_gateway)
        final_proxy_cmd = " ".join(inner_proxy_cmd)
        return f'-o ProxyCommand="{final_proxy_cmd}"'
    msg = "generate_ssh_option_gateway only supports up to 2 gateways for now"
    raise ValueError(msg)
