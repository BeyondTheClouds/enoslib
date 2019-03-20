# -*- coding: utf-8 -*-
from datetime import datetime
from functools import wraps
import os
import logging
import yaml

from enoslib.constants import SYMLINK_NAME
from enoslib.errors import EnosFilePathError

# Following this bug
# https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=10266
# we force the task to know about host
from enoslib.host import Host # noqa


logger = logging.getLogger(__name__)


def enostask(new=False):
    """Decorator for an Enos Task.

    This decorator lets you define a new Enos task and helps you manage the
    environment. It injects the environment in the function called.

    Args:
        new (bool): indicates if a new environment must be created.
            Usually this is set on the first task of the workflow.

    Examples:

        .. code-block:: python

            @enostask(new=True)
            def foo(env=None, **kwargs):
                # The key resultdir is available once the env is created
                print(env["resultdir"])

            @enostask()
            def myfunction(env=None, **kwargs):
                # saving a new key
                env['foo'] = 'bar'
    """
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            # Constructs the environment
            # --env or env are reserved keyword to reuse existing env
            k_env = kwargs.get("--env") or kwargs.get("env")
            if new:
                kwargs["env"] = _make_env(k_env)
                kwargs["env"]["resultdir"] = _set_resultdir(k_env)
                # the previous SYMLINK to the created result_dir
            else:
                kwargs["env"] = _make_env(k_env or SYMLINK_NAME)
            try:
                # Proceeds with the function execution
                logger.info("- Task %s started -" % fn.__name__)
                r = fn(*args, **kwargs)
                logger.info("- Task %s finished -" % fn.__name__)
                return r
            # Save the environment
            finally:
                _save_env(kwargs["env"])
        return decorated
    return decorator


def _make_env(resultdir=None):
    """Loads the env from `resultdir` if not `None` or makes a new one.

    An Enos environment handles all specific variables of an
    experiment. This function either generates a new environment or
    loads a previous one. If the value of `resultdir` is `None`, then
    this function makes a new environment and return it. If the value
    is a directory path that contains an Enos environment, then this function
    loads and returns it.

    In case of a directory path, this function also rereads the
    configuration file (the reservation.yaml) and reloads it. This
    lets the user update his configuration between each phase.

    Args:
        resultdir (str): directory path to load the env from.
    """
    env = {
        "config":      {},          # The config
        "resultdir":   "",          # Path to the result directory
        "config_file": "",          # The initial config file
        "nodes":       {},          # Roles with nodes
        "phase":       "",          # Last phase that have been run
        "user":        "",          # User id for this job
        "cwd":         os.getcwd()  # Current Working Directory
    }

    if resultdir:
        env_path = os.path.join(resultdir, "env")
        if os.path.isfile(env_path):
            with open(env_path, "r") as f:
                env.update(yaml.load(f))
                logger.debug("Loaded environment %s", env_path)

        if "config_file" in env and env["config_file"] is not None:
            # Resets the configuration of the environment
            if os.path.isfile(env["config_file"]):
                with open(env["config_file"], "r") as f:
                    env["config"].update(yaml.load(f))
                    logger.debug("Reloaded config %s", env["config"])

    return env


def _save_env(env):
    """Saves one environment.

    Args:
        env (dict): the env dict to save.
    """
    env_path = os.path.join(env["resultdir"], "env")

    if os.path.isdir(env["resultdir"]):
        with open(env_path, "w") as f:
            yaml.dump(env, f)


def _check_env(fn):
    """Decorator for an Enos Task.

    This decorator checks if an environment file exists.
    """
    def decorator(*args, **kwargs):
        # If no directory is provided, set the default one
        resultdir = kwargs.get("--env", SYMLINK_NAME)
        # Check if the env file exists
        env_path = os.path.join(resultdir, "env")
        if not os.path.isfile(env_path):
            raise Exception("The file %s does not exist." % env_path)

        # Proceeds with the function execution
        return fn(*args, **kwargs)
    return decorator


def _set_resultdir(name=None):
    """Set or get the directory to store experiment results.


    Looks at the `name` and create the directory if it doesn"t exist
    or returns it in other cases. If the name is `None`, then the
    function generates an unique name for the results directory.
    Finally, it links the directory to `SYMLINK_NAME`.

    Args:
        name (str): file path to an existing directory. It could be
            weather an absolute or a relative to the current working
            directory.

    Returns:
        the file path of the results directory.
    """
    # Compute file path of results directory
    resultdir_name = name or "enos_" + datetime.today().isoformat()
    resultdir_path = os.path.abspath(resultdir_name)

    # Raise error if a related file exists
    if os.path.isfile(resultdir_path):
        raise EnosFilePathError(resultdir_path,
                                "Result directory cannot be created due "
                                "to existing file %s" % resultdir_path)

    # Create the result directory if it does not exist
    if not os.path.isdir(resultdir_path):
        os.mkdir(resultdir_path)
        logger.info("Generate results directory %s" % resultdir_path)

    # Symlink the result directory with the "cwd/current" directory
    link_path = SYMLINK_NAME
    if os.path.lexists(link_path):
        os.remove(link_path)
    try:
        os.symlink(resultdir_path, link_path)
        logger.info("Symlink %s to %s" % (resultdir_path, link_path))
    except OSError:
        # An harmless error can occur due to a race condition when
        # multiple regions are simultaneously deployed
        logger.warning("Symlink %s to %s failed" %
                       (resultdir_path, link_path))

    return resultdir_path
