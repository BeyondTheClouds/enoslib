# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
import jsonschema


class Provider:
    __metaclass__ = ABCMeta

    def __init__(self, provider_conf):
        """Routine to validate the config against the schema."""
        self.provider_conf = provider_conf
        self.provider_conf.update(self.default_config())
        self.validate()

    @abstractmethod
    def init(self, force_deploy=False):
        """Provides resources and provisions the environment.

        The `config` parameter contains the client request (eg, number
        of compute per role among other things). This method returns,
        in this order, a list of the form [{Role: [Host]}], a dict to
        configure the network with `start` the first available ip,
        `end` the last available ip, `cidr` the network of available
        ips, the ip address of the `gateway` and the ip address of the
        `dns`, and a pair that contains the name of network and
        external interfaces.

        Args:
            config (dict): config of the provider. Specific to the underlying
                provider.
            force (bool): Indicates that the resources must be redeployed.

        Returns:
            tuple: (roles, networks, groups)
        """
        pass

    @abstractmethod
    def destroy(self):
        "Destroy the resources used for the deployment."
        pass

    @abstractmethod
    def default_config(self):
        """Default config for the provider config.

        Returns a dict with all keys used to initialize the provider
        (section `provider` of reservation.yaml file). Keys should be
        provided with a default value.
        """
        pass

    @abstractmethod
    def schema(self):
        """The jsonschema of the configuration."""

    def validate(self):
        """Validates the json schema."""
        jsonschema.validate(self.provider_conf, self.schema())
