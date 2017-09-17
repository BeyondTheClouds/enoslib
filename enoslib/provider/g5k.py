# -*- coding: utf-8 -*-
from deploy5k.api import Resources
from enoslib.host import Host
from enoslib.provider.provider import Provider
from netaddr import IPAddress, IPNetwork, IPSet

import logging

ROLE_DISTRIBUTION_MODE_STRICT = "strict"


def to_enos_roles(roles):
    """Transform the roles to use enoslib.host.Host hosts
    instead of dict

    :param roles: roles returned by deploy5k
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
    logging.debug(enos_roles)
    return enos_roles


def to_enos_networks(networks):
    nets = []
    for network in networks:
        net = {
            "cidr": str(network["network"]),
            "gateway": str(network["gateway"]),
            "dns": "131.254.203.235"
        }
        if network["vlan_id"]:
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
                #vlan local
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
        nets.append(net)
    logging.debug(nets)
    return nets


class G5k(Provider):
    def init(self, provider_conf):
        """Reserve and deploys the nodes accordina
        g to the resources section

        :param provider_conf: the provider config. It must contains a resource
        section and some other options specific to g5k.
        """
        resources = provider_conf["resources"]
        r = Resources(resources)
        r.launch(**provider_conf)
        roles = r.get_roles()
        networks = r.get_networks()
        return to_enos_roles(roles), to_enos_networks(networks)

    def destroy(self, provider_conf):
        # TODO(msimonin):implements destroy in deploy5k
        pass

    def default_config(self):
        return {
            'name': 'Enoslib',
            'walltime': '02:00:00',
            'env_name': 'jessie-x64-min',
            'reservation': False,
        }

    def __str__(self):
        return 'G5k'
