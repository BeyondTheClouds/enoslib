"""
Manage a configuration for EnOSlib.
"""
from contextlib import contextmanager
import copy
from typing import Any, Dict, Optional


_config = dict(g5k_cache=True, g5k_cache_dir="cachedir", display="html")


def get_config() -> Dict:
    """Get (a copy of) the current config."""
    return copy.deepcopy(_config)


def _set(key: str, value: Optional[Any]):
    if value is not None:
        _config[key] = value


def set_config(
    g5k_cache: Optional[bool] = None,
    g5k_cache_dir: Optional[str] = None,
    display: Optional[str] = None,
):
    """Set a specific config value.

    Args:
        g5k_cache: True iff a cache must be used for HTTP request to the API
            Reasons to disable the cache is to workaround issues with concurrent
            access on NFS.
        g5k_cache_dir: location of the g5k cache directory
    """
    _set("g5k_cache", g5k_cache)
    _set("g5k_cache_dir", g5k_cache_dir)
    _set("display", display)


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
