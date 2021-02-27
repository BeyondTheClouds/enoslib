# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod


class Provider:
    """Base class for the provider.

    Providers are components that are responsible for acquiring resources on
    existing testbeds. Concretely, a provider takes a declarative description
    of the expected resources as argument. It requests the resources on the
    corresponding testbed, and returns a set of hosts and networks labeled
    with their roles. In other words, providers help the experimenter deal
    with the variety of the APIs of testbeds.

    Example:

        Typical workflow:

            .. code-block:: python

                # craft a conf (provider specific)
                conf = Configuration() ...

                provider = Provider(conf)
                roles, networks = provider.init()

                # release resources
                provider.destroy()


        Using a context manager

            .. code-block:: python

                # craft a conf (provider specific)
                conf = Configuration() ...

                with provider(conf) as (roles, networks):
                    # do stuff with roles and networks
                    ...
                # Resources are automatically released at the end


    Args:
        provider_conf (BaseConfiguration): configuration of the provider.
            The configuration object is specific to each provider and must follow
            the provider's schema
    """

    __metaclass__ = ABCMeta

    def __init__(self, provider_conf):
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

    def __enter__(self):
        return self.init()

    def __exit__(self, *args):
        self.destroy()
