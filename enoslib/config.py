"""
Manage a configuration for EnOSlib.
"""
from contextlib import contextmanager
import copy
from pathlib import Path
from typing import Any, Dict, Optional, Union

import logging

logger = logging.getLogger(__name__)

_config = dict(
    g5k_cache="lru",
    display="html",
    dump_results=None,
    ansible_stdout="spinner",
)


def get_config() -> Dict:
    """Get (a copy of) the current config."""
    return copy.deepcopy(_config)


def _set(key: str, value: Optional[Any]):
    if value is not None:
        _config[key] = value


def _set_dump_results(dump_results: Optional[Union[Path, str]]):
    """Prechecks and set the dump_results key

    If the dump_results file exists, don't override it.
    Instead, add a suffix (.1 or .2 ...).

    Args:
        dump_results:  Path or str-path where the file results
            should be stored.

    """
    if dump_results is None:
        _set("dump_results", dump_results)
        return
    assert dump_results is not None

    candidate = str(dump_results)
    i = 1
    while Path(candidate).exists():
        candidate = f"{dump_results}.{i}"
        i += 1
    # we found a candidate, use it
    _set("dump_results", Path(candidate))


def set_config(
    g5k_cache: Optional[str] = None,
    display: Optional[str] = None,
    dump_results: Optional[Union[Path, str]] = None,
    ansible_stdout: Optional[str] = None,
):
    """Set a specific config value.

    Args:
        g5k_cache: True iff a cache must be used for HTTP request to the API
            Reasons to disable the cache is to workaround issues with concurrent
            access on NFS.
        g5k_cache_dir: location of the g5k cache directory
    """
    _set("g5k_cache", g5k_cache)
    _set("display", display)
    _set("ansible_stdout", ansible_stdout)
    _set_dump_results(dump_results)

    logger.debug("config = %s", get_config())


@contextmanager
def config_context(**new_config):
    """A context manager to manage a config specific to a portion of code.

    The original config is restored when exiting the context manager.

    Args:
        new_config: any keyword argument supported by
            :py:func:`~enoslib.config.set_config`

    Examples:

        .. code-block:: python

            from enoslib.config import config_context

            ...
            with config_context(g5k_cache=False):
                # let's disable the cache
                ...

            # the config goes back to its previous state here
    """
    old_config = get_config()
    set_config(**new_config)
    try:
        yield
    finally:
        set_config(**old_config)
