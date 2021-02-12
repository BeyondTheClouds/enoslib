from pathlib import Path
import os
from typing import Dict, List, Optional

from enoslib.api import play_on, __python3__
from enoslib.objects import Host
from ..service import Service
from ..utils import _check_path


OUTPUT_FILE = "dstat.csv"
TMUX_SESSION = "__enoslib_dstat__"

DOOL_URL = ("https://raw.githubusercontent.com/"
            "scottchiefbaker/dool/6b89f2d0b6e38e1c8d706e88a12e020367f5100d/dool")
DOOL_DIR = Path("/opt/enoslib_dool")
DOOL_PATH = DOOL_DIR / "dool"


class Dstat(Service):
    def __init__(
        self,
        *,
        nodes: List[Host],
        options: str = "",
        remote_working_dir: str = "/builds/dstat",
        priors: List[play_on] = [__python3__],
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
        self.priors = priors
        self.remote_working_dir = remote_working_dir
        self._roles = dict(all=self.nodes)

        # We force python3
        extra_vars = extra_vars if extra_vars is not None else {}
        self.extra_vars = {"ansible_python_interpreter": "/usr/bin/python3"}
        self.extra_vars.update(extra_vars)

    def deploy(self):
        """Deploy the dstat monitoring stack."""
        with play_on(
            roles=self._roles, priors=self.priors, extra_vars=self.extra_vars
        ) as p:
            p.apt(name=["tmux"], state="present")
            # install dool
            p.file(path=str(DOOL_DIR), state="directory")
            p.get_url(url=DOOL_URL, dest=str(DOOL_PATH), mode="0755")
            p.file(path=self.remote_working_dir, recurse="yes", state="directory")
            options = f"{self.options} -o {OUTPUT_FILE}"
            p.shell(
                (
                    f"(tmux ls | grep {TMUX_SESSION}) || "
                    f"tmux new-session -s {TMUX_SESSION} "
                    f"-d 'exec {DOOL_PATH} {options}'"
                ),
                chdir=self.remote_working_dir,
                display_name=f"Running dstat with the options {options}",
            )

    def destroy(self):
        """Destroy the dtsat monitoring stack.

        This kills the dstat processes on the nodes.
        Metric files survive to destroy.
        """
        with play_on(roles=self._roles, extra_vars=self.extra_vars) as p:
            kill_cmd = f"tmux kill-session -t {TMUX_SESSION}"
            p.shell(kill_cmd)

    def backup(self, backup_dir: Optional[str] = None):
        """Backup the dstat monitoring stack.

        This fetches all the remote dstat csv files under the backup_dir.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        if backup_dir is None:
            _backup_dir = Path.cwd()
        else:
            _backup_dir = Path(backup_dir)

        _backup_dir = _check_path(_backup_dir)

        with play_on(roles=self._roles, extra_vars=self.extra_vars) as p:
            backup_path = os.path.join(self.remote_working_dir, OUTPUT_FILE)
            p.fetch(
                display_name="Fetching the dstat output",
                src=backup_path,
                dest=str(Path(_backup_dir, "dstat")),
                flat=False,
            )
