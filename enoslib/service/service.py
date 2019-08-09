from abc import ABCMeta, abstractmethod
import os


SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


class Service:
    """A service is a reusable piece of software."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def deploy(self):
        pass

    @abstractmethod
    def destroy(self):
        pass

    @abstractmethod
    def backup(self):
        pass
