# -*- coding: utf-8 -*-
import logging

import enoslib.infra.enos_g5k.api as api
from enoslib.host import Host
from enoslib.infra.provider import Provider


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
    for roles, network in networks:
        # each network is a list (see utils.concretize_networks)
        nets.extend([n.to_enos(roles) for n in network])
    logger.debug(nets)
    return nets


class G5k(Provider):
    """The provider to use when deploying on Grid'5000."""

    def init(self, force_deploy=False, client=None):
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
        _force_deploy = self.provider_conf.force_deploy
        self.provider_conf.force_deploy = _force_deploy or force_deploy
        self._provider_conf = self.provider_conf.to_dict()
        r = api.Resources(self._provider_conf, client=client)
        r.launch()
        roles = r.get_roles()
        networks = r.get_networks()

        return (_to_enos_roles(roles),
                _to_enos_networks(networks))

    def destroy(self):
        """Destroys the jobs."""
        r = api.Resources(self.provider_conf.to_dict())
        # insert force_deploy
        r.destroy()

    def __str__(self):
        return 'G5k'
