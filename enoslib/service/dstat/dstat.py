from pathlib import Path
import os
from time import time
from typing import Dict, List

from enoslib.api import play_on, bg_start, bg_stop
from enoslib.objects import Host, Roles
from ..service import Service
from ..utils import _check_path


OUTPUT_FILE = "dstat.csv"
TMUX_SESSION = "__enoslib_dstat__"

DOOL_URL = (
    "https://raw.githubusercontent.com/"
    "scottchiefbaker/dool/02b1c69d441764b030db5e78b4b6fb231c29f8f1/dool"
)

REMOTE_OUTPUT_DIR = Path("/tmp/__enoslib_dstat__")
DOOL_PATH = REMOTE_OUTPUT_DIR / "dool"
LOCAL_OUTPUT_DIR = Path("__enoslib_dstat__")


class Dstat(Service):
    def __init__(
        self,
        *,
        nodes: List[Host],
        options: str = "-aT",
        backup_dir: Path = LOCAL_OUTPUT_DIR,
        extra_vars: Dict = None,
    ):
        """Deploy dstat on all hosts.

        This assumes a debian/ubuntu based environment and aims at producing a
        quick way to deploy a simple monitoring stack based on dstat on your nodes.
        It's opinionated out of the box but allow for some convenient customizations.

        dstat metrics are dumped into a csv file by default (-o option) and
        retrieved when backuping.


        Args:
            nodes: the nodes to install dstat on
            options: options to pass to dstat.
            priors : priors to apply
            extra_vars: extra vars to pass to Ansible


        Examples:

            .. literalinclude:: examples/dstat.py
                :language: python
                :linenos:


        """
        self.nodes = nodes
        self.options = options
        self.remote_working_dir = Path(REMOTE_OUTPUT_DIR)
        self._roles = Roles(all=self.nodes)

        self.backup_dir = Path(backup_dir)
        self.backup_dir = _check_path(self.backup_dir)

        # generate output file name by default dstat append to the existing file
        # which isn't very convenient at parsing time we could also add some
        # prefix to differentiate from different calls to this service in the
        # same xp
        self.output_file = f"{time()}-{OUTPUT_FILE}"

        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

    def deploy(self, force=False):
        """Deploy the dstat monitoring stack."""
        if force:
            self.destroy()
        with play_on(
            roles=self._roles, extra_vars=self.extra_vars
        ) as p:
            p.apt(name=["tmux"], state="present")
            # install dool
            p.file(path=str(self.remote_working_dir), state="directory", recurse="yes")
            p.get_url(url=DOOL_URL, dest=str(DOOL_PATH), mode="0755")
            options = f"{self.options} -o {self.output_file}"
            p.shell(
                bg_start(TMUX_SESSION, f"python3 {str(DOOL_PATH)} {options}"),
                chdir=str(self.remote_working_dir),
                display_name=f"Running dstat with the options {options}",
            )

    def destroy(self):
        """Destroy the dtsat monitoring stack.

        This kills the dstat processes on the nodes.
        Metric files survive to destroy.
        """
        with play_on(roles=self._roles, extra_vars=self.extra_vars) as p:
            kill_cmd = bg_stop(TMUX_SESSION)
            p.shell(kill_cmd)

    def backup(self):
        """Backup the dstat monitoring stack.

        This fetches all the remote dstat csv files under the backup_dir.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        with play_on(roles=self._roles, extra_vars=self.extra_vars) as p:
            backup_path = os.path.join(self.remote_working_dir, self.output_file)
            p.fetch(
                display_name="Fetching the dstat output",
                src=backup_path,
                dest=str(self.backup_dir),
                flat=False,
            )

    def __enter__(self):
        self.deploy(force=True)
        return self