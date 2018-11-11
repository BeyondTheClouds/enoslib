# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod


class Provider:
    """Base class for all providers."""
    __metaclass__ = ABCMeta

    def __init__(self, provider_conf):
        """The constructor takes care of loading the configuration.

        Args:
            provider_conf (BaseConfiguration): configuration of the provider.
        The configuration object is specific to each provider and must follow
        the provider's schema
        """
        self.provider_conf = provider_conf

    @abstractmethod
    def init(self, force_deploy=False):
        """Abstract. Provides resources and provisions the environment.

        This calls the underlying provider and provision resources (machines
        and networks).

        Args:
            force_deploy (bool): Indicates that the resources must be
                redeployed.

        Returns:
            (roles, networks) tuple: roles is a dict whose key is a role and
            the value is the machines associated with this role. networks is
            the list of networks configured by the provider. see
            :py:class:`~enoslib.infra.enos_vagrant.provider.Enos_vagrant`"""
        pass

    @abstractmethod
    def destroy(self):
        "Abstract. Destroy the resources used for the deployment."
        pass
