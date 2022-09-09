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

    def __enter__(self):
        self.destroy()
        self.deploy()
        return self

    def __exit__(self, *args):
        # should we destroy before backuping: that's the question in some cases
        # yes in some other cases no, so we give a default implementation here
        # which will fit the dstat, tcpdump ... use case (we want to send the
        # SIGX signal to the process to trigger the flush of the data to the
        # disk before backuping)
        # For some other cases like (online) TIGmonitoring we want the database
        # to be up while backuping so destroy should occur after.
        self.destroy()
        self.backup()
