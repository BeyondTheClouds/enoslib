from typing import List
import logging
from enoslib.objects import DefaultNetwork
from enoslib.infra.enos_chameleonedge.chameleon_api import ChameleonAPI

logger = logging.getLogger(__name__)


class ChameleonDevice:
    """
    A Chameleon edge device
    """

    def __init__(
        self,
        address: str,
        roles: List[str],
        uuid: str,
        rc_file: str,
    ):
        # read only attributes
        self.address = address
        self.roles = roles
        self.uuid = uuid
        self.rc_file = rc_file
        self.client = ChameleonAPI()

    def __repr__(self):
        return (
            "<ChameleonDevice("
            f"address={self.address}, "
            f"roles={self.roles}, "
            f"uuid={self.uuid})>, "
            f"rc_file={self.rc_file})>"
        )

    def execute(self, command: str):
        return self.client.execute(self.uuid, self.rc_file, command)

    def upload(self, source: str, dest: str):
        return self.client.upload(self.uuid, self.rc_file, source, dest)

    def download(self, source: str, dest: str):
        return self.client.download(self.uuid, self.rc_file, source, dest)

    def associate_floating_ip(self):
        return self.client.associate_floating_ip(self.uuid, self.rc_file)

    def destroy_container(self):
        return self.client.destroy_container(self.uuid, self.rc_file)

    def get_logs(self, stdout: bool = True, stderr: bool = True):
        return self.client.get_logs(self.uuid, self.rc_file, stdout, stderr)

    def snapshot_container(self, repository: str, tag: str = "latest"):
        return self.client.snapshot_container(self.uuid, self.rc_file, repository, tag)


class ChameleonNetwork(DefaultNetwork):
    """Chameleon network class."""

    def __init__(self, roles: List[str], *args, **kargs):
        super().__init__(*args, **kargs)
        self.roles = roles
