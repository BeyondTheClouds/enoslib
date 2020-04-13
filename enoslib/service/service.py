from abc import ABCMeta, abstractmethod
import os


SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class Service:
    """A service is a reusable piece of software."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def deploy(self):
        """(abstract) Deploy the service."""
        pass

    @abstractmethod
    def destroy(self):
        """(abstract) Destroy the service."""
        pass

    @abstractmethod
    def backup(self):
        """(abstract) Backup the service."""
        pass
