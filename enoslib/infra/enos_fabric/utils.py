import contextlib
import logging
import os
from pathlib import Path
from typing import Generator, Union

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def source_credentials_from_rc_file(
    rc_file: Union[Path, str],
) -> Generator[None, None, None]:
    initial_env = os.environ.copy()
    with open(rc_file) as file:
        lines = file.readlines()
        for line in lines:
            if "export" in line:
                key = line.split("=")[0].split(" ")[1]
                value = line.split("=")[1].strip().replace('"', "")
                os.environ[key] = value
    try:
        yield None
    except Exception as err:
        raise Exception(err) from err
    finally:
        # change env back to its initial state
        os.environ.clear()
        os.environ.update(initial_env)
