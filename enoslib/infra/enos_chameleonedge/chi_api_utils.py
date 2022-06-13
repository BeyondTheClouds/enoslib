import os
import contextlib
import logging
import chi
from enoslib.infra.enos_chameleonedge.constants import OS_WHITE_LIST_DEBUG

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(rc_file):
    initial_env = os.environ.copy()
    with open(rc_file) as file:
        lines = file.readlines()
        for line in lines:
            if "export" in line:
                key = line.split('=')[0].split(' ')[1]
                value = line.split('=')[1].strip()
                os.environ[key] = value
                if key in OS_WHITE_LIST_DEBUG:
                    logger.debug(f"{key}={os.environ[key]}")
    chi.context.reset()
    site = os.environ["OS_REGION_NAME"].replace('"', '')
    try:
        yield site
    except Exception as e:
        raise Exception(e)
    finally:
        # change env back to its initial state
        os.environ.clear()
        os.environ.update(initial_env)


def check_connection_to_api(rc_file: str):
    with source_credentials_from_rc_file(rc_file) as _site:
        try:
            chi.use_site(_site)
            chi.blazar().lease.list()
            return f"Successfully connected to {_site}!"
        except Exception:
            raise Exception(f"Failed to connect to {_site}!")
