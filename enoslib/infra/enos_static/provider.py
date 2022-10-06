from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.infra.provider import Provider


class Static(Provider):
    """The Static provider class.

    This class is used when one has already machines and network configured.
    This is useful when there is no provider class corresponding the user
    testbed. To use it the user must build a configuration object that reflects
    the exact settings of his machines and networks.
    """

    def init(self, force_deploy=False, **kwargs):
        machines = self.provider_conf.machines
        roles = Roles()
        for machine in machines:
            for r in machine.roles:
                roles[r] += [
                    Host(
                        machine.address,
                        alias=machine.alias,
                        user=machine.user,
                        keyfile=machine.keyfile,
                        port=machine.port,
                        extra=machine.extra,
                    )
                ]

        networks = Networks()
        for n in self.provider_conf.networks:
            for role in n.roles:
                networks[role] += [
                    DefaultNetwork(
                        address=n.cidr,
                        gateway=n.gateway,
                        dns=n.dns,
                        ip_start=n.start,
                        ip_end=n.end,
                    )
                ]

        return roles, networks

    def destroy(self, wait=False):
        pass

    def offset_walltime(self, difference: int):
        raise NotImplementedError(
            "Please Implement me to enjoy the power of multi platforms experiments."
        )
