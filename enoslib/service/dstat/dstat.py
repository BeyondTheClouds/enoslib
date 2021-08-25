from enoslib.html import (
    dict_to_html_foldable_sections,
    html_from_sections,
    html_to_foldable_section,
    repr_html_check,
)
from pathlib import Path
import os
from time import time_ns
from typing import Dict, List, Optional

from enoslib.api import play_on, bg_start, bg_stop
from enoslib.objects import Host
from ..service import Service
from ..utils import _set_dir


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
        backup_dir: Optional[Path] = None,
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
        # make it unique per instance
        identifier = str(time_ns())
        self.remote_working_dir = Path(REMOTE_OUTPUT_DIR) / identifier

        # make it unique per instance
        self.backup_dir = _set_dir(backup_dir, LOCAL_OUTPUT_DIR / identifier)

        self.output_file = f"{identifier}-{OUTPUT_FILE}"

        self.extra_vars = extra_vars if extra_vars is not None else {}

    def deploy(self):
        """Deploy the dstat monitoring stack."""
        with play_on(roles=self.nodes, extra_vars=self.extra_vars) as p:
            p.apt(name=["tmux"], state="present")
            # install dool
            p.file(path=str(self.remote_working_dir), state="directory", recurse="yes")
            p.get_url(url=DOOL_URL, dest=str(DOOL_PATH), mode="0755")
            options = f"{self.options} -o {self.output_file}"
            p.shell(
                bg_start(TMUX_SESSION, f"python3 {str(DOOL_PATH)} {options}"),
                chdir=str(self.remote_working_dir),
                task_name=f"Running dstat with the options {options}",
            )

    def destroy(self):
        """Destroy the dtsat monitoring stack.

        This kills the dstat processes on the nodes.
        Metric files survive to destroy.
        """
        with play_on(roles=self.nodes, extra_vars=self.extra_vars) as p:
            kill_cmd = bg_stop(TMUX_SESSION)
            p.shell(kill_cmd)

    def backup(self, backup_dir: Optional[Path] = None):
        """Backup the dstat monitoring stack.

        This fetches all the remote dstat csv files under the backup_dir.

        Args:
            backup_dir (str): path of the backup directory to use.
        """
        _backup_dir = _set_dir(backup_dir, self.backup_dir)
        with play_on(roles=self.nodes, extra_vars=self.extra_vars) as p:
            backup_path = os.path.join(self.remote_working_dir, self.output_file)
            p.fetch(
                task_name="Fetching the dstat output",
                src=backup_path,
                dest=str(_backup_dir),
                flat=False,
            )

    @repr_html_check
    def _repr_html_(self, content_only=False):
        def hosts_as_foldable_section(hosts):
            sections = [
                html_to_foldable_section(h.alias, h._repr_html_()) for h in hosts
            ]
            return sections

        sections = []
        sections.append(
            html_to_foldable_section(
                "nodes", hosts_as_foldable_section(self.nodes), len(self.nodes)
            )
        )
        d = dict(self.__dict__)
        d.pop("nodes")
        sections.append(dict_to_html_foldable_sections(d))
        return html_from_sections(
            str(self.__class__), sections, content_only=content_only
        )
