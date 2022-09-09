import contextlib
import os
import logging

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(rc_file):
    initial_env = os.environ.copy()
    with open(rc_file) as file:
        lines = file.readlines()
        for line in lines:
            if "export" in line:
                key = line.split("=")[0].split(" ")[1]
                value = line.split("=")[1].strip().replace('"', "")
                os.environ[key] = value
                if key in ["OS_AUTH_TYPE", "OS_AUTH_URL", "OS_REGION_NAME"]:
                    logger.debug(f"{key}={os.environ[key]}")
    site = os.environ["OS_REGION_NAME"].replace('"', "")
    # The following avoids:
    # Unauthorized: Error authenticating with application credential:
    # Application credentials cannot request a scope: 'OS_PROJECT_NAME'.
    if os.environ["OS_AUTH_TYPE"] in ["v3applicationcredential"]:
        os.environ["OS_PROJECT_NAME"] = ""
    try:
        yield site
    except Exception as e:
        raise Exception(e)
    finally:
        # change env back to its initial state
        os.environ.clear()
        os.environ.update(initial_env)
