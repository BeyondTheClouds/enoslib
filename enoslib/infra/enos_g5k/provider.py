# -*- coding: utf-8 -*-

import enoslib.infra.enos_g5k.api as api
from .constants import NAMESERVER
from enoslib.infra.enos_g5k.schema import KAVLAN_TYPE, SUBNET_TYPE
from enoslib.host import Host
from enoslib.infra.provider import Provider
from enoslib.utils import get_roles_as_list

from netaddr import IPAddress, IPNetwork, IPSet
import logging
import socket


logger = logging.getLogger(__name__)


def _to_enos_roles(roles):
    """Transform the roles to use enoslib.host.Host hosts.

    Args:
        roles (dict): roles returned by
            :py:func:`enoslib.infra.provider.Provider.init`
    """

    def to_host(h):
        extra = {}
        # create extra_vars for the nics
        # network_role = ethX
        for nic, roles in h["nics"]:
            for role in roles:
                extra[role] = nic

        return Host(h["host"], user="root", extra=extra)

    enos_roles = {}
    for role, hosts in roles.items():
        enos_roles[role] = [to_host(h) for h in hosts]
    logger.debug(enos_roles)
    return enos_roles


def _to_enos_networks(networks):
    """Transform the networks returned by deploy5k.

    Args:
        networks (dict): networks returned by
            :py:func:`enoslib.infra.provider.Provider.init`
    """
    nets = []
    for network in networks:
        net = {
            "cidr": str(network["network"]),
            "gateway": str(network["gateway"]),
            # NOTE(msimonin): This will point to the nameserver of the site
            # where the deployment is launched regardless the actual site in
            # the network description. Until now we used the global DNS IP
            # here. Finally this information couldn't be found in the API (dec.
            # 18) otherwise we'd move this logic in utils.concretize_networks
            # (like network and gateway)
            "dns": socket.gethostbyname(NAMESERVER),
            "roles": get_roles_as_list(network)
        }
        if network["type"] in KAVLAN_TYPE:
            # On the network, the first IP are reserved to g5k machines.
            # For a routed vlan I don't know exactly how many ip are
            # reserved. However, the specification is clear about global
            # vlan: "A global VLAN is a /18 subnet (16382 IP addresses).
            # It is split -- contiguously -- so that every site gets one
            # /23 (510 ip) in the global VLAN address space". There are 12
            # site. This means that we could take ip from 13th subnetwork.
            # Lets consider the strategy is the same for routed vlan. See,
            # https://www.grid5000.fr/mediawiki/index.php/Grid5000:Network#KaVLAN
            #
            # First, split network in /23 this leads to 32 subnetworks.
            # Then, (i) drops the 12 first subnetworks because they are
            # dedicated to g5k machines, and (ii) drops the last one
            # because some of ips are used for specific stuff such as
            # gateway, kavlan server...
            subnets = IPNetwork(network["network"])
            if network["vlan_id"] < 4:
                # vlan local
                subnets = list(subnets.subnet(24))
                subnets = subnets[4:7]
            else:
                subnets = list(subnets.subnet(23))
                subnets = subnets[13:31]

            # Finally, compute the range of available ips
            ips = IPSet(subnets).iprange()

            net.update({
                "start": str(IPAddress(ips.first)),
                "end": str(IPAddress(ips.last))
            })
        elif network["type"] in SUBNET_TYPE:
            start_ip, start_mac = network["ipmac"][0]
            end_ip, end_mac = network["ipmac"][-1]
            net.update({
                "start": start_ip,
                "end": end_ip,
                "mac_start": start_mac,
                "mac_end": end_mac
            })

        net.update({"roles": get_roles_as_list(network)})
        nets.append(net)
    logger.debug(nets)
    return nets


class G5k(Provider):
    """The provider to use when deploying on Grid'5000."""

    def init(self, force_deploy=False):
        """Reserve and deploys the nodes according to the resources section

        In comparison to the vagrant provider, networks must be characterized
        as in the networks key.

        Args:
            force_deploy (bool): True iff the environment must be redeployed
        Raises:
            MissingNetworkError: If one network is missing in comparison to
                what is claimed.
            NotEnoughNodesError: If the `min` constraints can't be met.

           """
        self.provider_conf.force_deploy = force_deploy

        # TODO remove the use of dict
        self._provider_conf = self.provider_conf.to_dict()
        r = api.Resources(self._provider_conf)
        r.launch()
        roles = r.get_roles()
        networks = r.get_networks()

        return (_to_enos_roles(roles),
                _to_enos_networks(networks))

    def destroy(self):
        """Destroys the jobs."""
        r = api.Resources(self._provider_conf)
        # insert force_deploy
        r.destroy()

    def __str__(self):
        return 'G5k'
