from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import tempfile
import os
import yaml

from ddt import ddt, data

from . import EnosTest
from enoslib.task import Environment, _symlink_to, get_or_create_env, enostask
from enoslib.constants import ENV_FILENAME, SYMLINK_NAME
from enoslib.errors import EnosFilePathError


@contextmanager
def into_tmp_dir():
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            yield tmp_dir
        except Exception as e:
            raise e
        finally:
            os.chdir(old_cwd)


def create_env(env_name, symlink=True):
    env = Environment(Path(env_name))
    if symlink:
        _symlink_to(Path(env_name))
    # this dumps in {env_name}/env
    env.dump()
    return env


@contextmanager
def dummy_env(env_name, symlink=True):
    """A context manager that creates an env in the current directory."""
    # create it and dump it
    with into_tmp_dir() as tmp_dir:
        env = create_env(env_name, symlink=symlink)
        yield (env, tmp_dir)


def dir_with_env(env_name, *top_args, symlink=True):
    def _dir_with_env(f):
        def wrapped(*args, **kwargs):
            with dummy_env(env_name, symlink=symlink) as (env, tmp_dir):
                f(*args, *top_args, Path(tmp_dir), env, **kwargs)
            # not restoring the cwd make py.test lose her mind

        return wrapped

    return _dir_with_env


def dir_without_env(f):
    def wrapped(*args, **kwargs):
        with into_tmp_dir() as tmp_dir:
            # create a dummy env there
            f(*args, Path(tmp_dir), **kwargs)

    return wrapped


class TestGetOrCreateEnvironment(EnosTest):
    @dir_with_env("xp1")
    def test_reload_existing(self, directory, env):
        actual_env = get_or_create_env(False, env)
        self.assertEqual(actual_env, env)

    @patch.object(Environment, "load_from_file")
    def test_reload_from_file(self, mock_load_from_file):
        p = Path("/path/to/env_dir")
        _ = get_or_create_env(False, p)
        mock_load_from_file.assert_called_once_with(p.joinpath(ENV_FILENAME))

    @dir_with_env("xp1")
    def test_reload_default(self, directory, env):
        _ = SYMLINK_NAME.joinpath(ENV_FILENAME)
        actual_env = get_or_create_env(False, None)
        # we got two different objects here
        self.assertEqual(env.env_name, actual_env.env_name)

    @dir_without_env
    def test_reload_create_new(self, dir_without_env):
        actual_env = get_or_create_env(True, None)
        self.assertTrue(Path.cwd().joinpath(SYMLINK_NAME).is_symlink())
        self.assertTrue("enos_" in str(actual_env.env_name))

    @dir_without_env
    def test_reload_create_new_predefined(self, dir_without_env):
        actual_env = get_or_create_env(True, "xp1")
        self.assertTrue(Path.cwd().joinpath(SYMLINK_NAME).is_symlink())
        self.assertEqual(Path("xp1").resolve(), actual_env.env_name)

    @dir_without_env
    def test_reload_reload_not_existing(self, dir_without_env):
        with self.assertRaises(EnosFilePathError) as _:
            _ = get_or_create_env(False, None)

    @dir_without_env
    def test_reload_manage_several_env(self, dir_without_env):
        create_env("xp1", symlink=True)
        create_env("xp2", symlink=True)

        self.assertTrue(SYMLINK_NAME.is_dir())
        self.assertEqual(dir_without_env.joinpath("xp2"), SYMLINK_NAME.resolve())

        # no symlink is done in this case
        actual_env = get_or_create_env(False, Path("xp1"))
        self.assertTrue(SYMLINK_NAME.is_dir())
        self.assertEqual(dir_without_env.joinpath("xp2"), SYMLINK_NAME.resolve())
        self.assertEqual(Path("xp1").resolve(), actual_env.env_name)


class TestConfig(EnosTest):
    @dir_with_env("xp1")
    def test_reload_no_config(self, directory, env):
        env.reload_config()
        self.assertEqual(None, env["config_file"])

    @dir_with_env("xp1")
    def test_reload_config(self, directory, env):
        conf = {"foo": "bar"}
        with Path("myconf.yaml").open("w") as f:
            f.write(yaml.dump(conf))
        env["config_file"] = "myconf.yaml"
        env.reload_config()
        self.assertEqual("bar", env["config"]["foo"])


@ddt
class TestEnosTask(EnosTest):
    @dir_with_env("xp1", symlink=True)
    def test_decorator_autoreload(self, dir_with_env, env):
        @enostask(new=False)
        def mytask(env=None):
            pass

        mytask()

    @dir_with_env("xp1", symlink=False)
    def test_decorator_autoreload_raise_if_no_current(self, dir_with_env, env):
        @enostask(new=False)
        def mytask(env=None):
            pass

        with self.assertRaises(EnosFilePathError) as _:
            mytask()

    @data(None, "xp1", Path("xp1"))
    @dir_with_env("xp1", symlink=True)
    def test_decorator_nested_current(self, env_specifier, dir_with_env, env):
        @enostask()
        def nested_task(env=None):
            self.assertEqual(dir_with_env.joinpath("xp1"), env.env_name)
            self.assertEqual("bar", env["foo"])

        @enostask()
        def top_task(env=None):
            env["foo"] = "bar"
            nested_task(env=env)

        top_task(env=env_specifier)

    # test with absolute path
    @data(True, False)
    def test_decorator_nested_current_absolute_path(self, symlink):
        @enostask()
        def nested_task(env=None):
            self.assertEqual(Path("xp1").resolve(), env.env_name)
            self.assertEqual("bar", env["foo"])

        @enostask()
        def top_task(env=None):
            env["foo"] = "bar"
            nested_task(env=env)

        with dummy_env("xp1", symlink=symlink) as _:
            # abs path here
            top_task(env=Path("xp1").resolve())

    @data("xp1", Path("xp1"))
    @dir_with_env("xp1", symlink=False)
    def test_decorator_nested_nocurrent(self, env_specifier, dir_with_env, env):
        @enostask()
        def nested_task(env=None):
            self.assertEqual(dir_with_env.joinpath("xp1"), env.env_name)
            self.assertEqual("bar", env["foo"])

        @enostask()
        def top_task(env=None):
            env["foo"] = "bar"
            nested_task(env=env)

        # specifying an env as a string (relative path)
        top_task(env=env_specifier)
