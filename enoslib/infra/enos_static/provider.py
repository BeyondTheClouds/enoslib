# -*- coding: utf-8 -*-
from collections import defaultdict

from enoslib.objects import DefaultNetwork, Host
from enoslib.infra.provider import Provider


class Static(Provider):
    """The Static provider class.

    This class is used when one has already machines and network configured.
    This is usefull when there si no provider class corresponding the user
    testbed. To use it the user must build a configuration object that reflects
    the exact settings of his machines and networks.
    """

    def init(self, force_deploy=False):
        machines = self.provider_conf.machines
        roles = defaultdict(list)
        for machine in machines:
            for r in machine.roles:
                roles.setdefault(r, []).append(
                    Host(
                        machine.address,
                        alias=machine.alias,
                        user=machine.user,
                        keyfile=machine.keyfile,
                        port=machine.port,
                        extra=machine.extra,
                    )
                )

        networks = defaultdict(list)
        for n in self.provider_conf.networks:
            for role in n.roles:
                networks[role].append(
                    DefaultNetwork(
                        address=n.cidr,
                        gateway=n.gateway,
                        dns=n.dns,
                        ip_start=n.start,
                        ip_end=n.end,
                    )
                )

        return roles, networks

    def destroy(self):
        pass
