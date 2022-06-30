import contextlib
import logging
import chi
from enoslib.infra.enos_openstack import utils
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(rc_file):
    with utils.source_credentials_from_rc_file(rc_file) as site:
        chi.context.reset()
        chi.use_site(site)
        yield site


def check_connection_to_api(rc_file: str):
    with source_credentials_from_rc_file(rc_file) as _site:
        try:
            chi.blazar().lease.list()
            return f"Successfully connected to {_site}!"
        except Exception:
            raise Exception(f"Failed to connect to {_site}!")
