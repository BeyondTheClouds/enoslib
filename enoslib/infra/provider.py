# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
import jsonschema


class Provider:
    """Base class for all providers."""
    __metaclass__ = ABCMeta

    def __init__(self, provider_conf):
        """
        The constructor takes care of loading the configuration and applying
        the default parameters given by
        :py:meth:`~enoslib.infra.provider.Provider.default_config`.
        The resulting configuration is then validated using the
        :py:meth:`~enoslib.infra.provider.validate` method.

        Args:
            provider_conf (dict): config of the provider. Specific to the
                underlying provider.
        """
        self.provider_conf = provider_conf
        self.provider_conf = self.default_config()
        self.provider_conf.update(provider_conf)
        self.validate()

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

    @abstractmethod
    def default_config(self):
        """Abstract. Default config for the provider config.

        Returns a dict with all keys used to initialize the provider
        (section `provider` of reservation.yaml file). Keys should be
        provided with a default value.
        """
        pass

    @abstractmethod
    def schema(self):
        """Abstract. Returns the schema of the provider config"""

    def validate(self):
        """Validates the configuration.

        By default validate the jsonschema.
        """
        jsonschema.validate(self.provider_conf, self.schema())
