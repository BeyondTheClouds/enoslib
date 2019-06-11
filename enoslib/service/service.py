from abc import ABCMeta, abstractmethod


class Service:
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
