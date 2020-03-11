from pathlib import Path
import os
from typing import List, Optional

from enoslib.api import play_on, __python3__, __default_python3__
from enoslib.types import Host
from ..service import Service
from ..utils import _check_path


OUTPUT_FILE = "dstat.csv"


class Dstat(Service):
    def __init__(
        self,
        *,
        nodes: List[Host],
        options: str = "",
        remote_working_dir: str = "/builds/dstat",
        priors: List[play_on] = [__python3__, __default_python3__],
    ):
        """Deploy dstat on all hosts.

        This assumes a debian/ubuntu base environment and aims at producing a
        quick way to deploy a simple monitoring stack based on dstat on your nodes.
        It's opinionated out of the box but allow for some convenient customizations.

        dstat metrics are dumped into a csv file by default (-o option) and
        retrieved when backuping.


        Args:
            nodes: the nodes to install dstat on
            options: options to pass to dstat.
            priors : priors to apply


        Examples:

            .. literalinclude:: examples/dtsat.py
                :language: python
                :linenos:


        """
        self.nodes = nodes
        self.options = options
        self.priors = priors
        self.remote_working_dir = remote_working_dir
        self._roles = dict(all=self.nodes)

    def deploy(self):
        """Deploy the dstat monitoring stack."""
        with play_on(roles=self._roles, priors=self.priors) as p:
            p.apt(name=["dstat", "tmux"], state="present")
            p.file(path=self.remote_working_dir, recurse="yes", state="directory")
            options = f"{self.options} -o {OUTPUT_FILE}"
            p.shell(
                f"tmux new-session -d 'exec dstat {options}'",
                chdir=self.remote_working_dir,
                display_name=f"Running dstat with the options {options}",
            )

    def destroy(self):
        """Destroy the dtsat monitoring stack.

        This kills the dstat processes on the nodes.
        Metric files survive to destroy.
        """
        """Stop locust."""
        with play_on(roles=self._roles) as p:
            kill_cmd = []
            kill_cmd.append('kill -9 `ps aux|grep "dstat"')
            kill_cmd.append("grep -v grep")
            kill_cmd.append('sed "s/ \\{1,\\}/ /g"')
            kill_cmd.append('cut -f 2 -d" "`')
            p.shell("|".join(kill_cmd) + "|| true")

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

        with play_on(roles=self._roles) as p:
            backup_path = os.path.join(self.remote_working_dir, OUTPUT_FILE)
            p.fetch(
                display_name="Fetching the dstat output",
                src=backup_path,
                dest=str(Path(_backup_dir, "dstat")),
                flat=False,
            )
