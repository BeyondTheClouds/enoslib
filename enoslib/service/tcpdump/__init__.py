from pathlib import Path
from typing import Iterable, List, Optional, Union


from enoslib.api import play_on, bg_start, bg_stop
from enoslib.objects import Host, Network, Roles
from ..service import Service
from ..utils import _set_dir


REMOTE_OUTPUT_DIR = "/tmp/__enoslib_tcpdump__"
LOCAL_OUTPUT_DIR = "__enoslib_tcpdump__"


class TCPDump(Service):
    def __init__(
        self,
        hosts: Iterable[Host],
        ifnames: Optional[List[str]] = None,
        networks: Optional[Iterable[Network]] = None,
        options: str = "",
        backup_dir: Union[Path, str] = None,
    ):
        """Monitor network traffic using tcpdump.

        This connects to every host to launch as many tcpdump processes as
        network interfaces to monitor.  The pcap files can be retrieved and
        analysed by your favorite tool (wireshark, scappy ...).  Each tcpdump
        process is launched in the background using a dedicated tmux session.

        Can be used as a Context Manager. In this case, the pcap files are
        retrieved automatically when exiting and all the remaining tcpdump
        processes are killed.

        Note that if networks is used, :py:func:`~enoslib.api.sync_info` must
        have been called before.

        Args:
            hosts: list of hosts to consider
            ifnames: explicit network card names to monitor.
                "any" is a possible keyword that will monitor all interfaces.
            networks: monitor all interfaces that belong to one of those networks
            options: extra options to pass to tcpdump command line.
            backup_dir: path to a local directory where the pcap files will be saved

        Examples:

            .. literalinclude:: examples/tcpdump.py
                    :language: python
                    :linenos:
        """
        self.hosts = hosts
        self.ifnames = ifnames if ifnames else []
        self.networks = networks if networks else []
        self.roles = Roles(all=hosts)
        self._tmux_sessions_maps = [(s, s) for s in self.ifnames]
        self.backup_dir = _set_dir(backup_dir, LOCAL_OUTPUT_DIR)
        self.options = options

        # handle networks
        for host in hosts:
            ifs = []
            if self.networks:
                ifs = host.filter_interfaces(self.networks)
            host.extra.update(tcpdump_ifs=ifs)

    def deploy(self, force=False):
        with play_on(roles=self.roles, gather_facts=True) as p:
            p.apt(
                name=["tcpdump", "tmux"],
                state="present",
                task_name="Install dependencies (tcpdump, tmux ...)",
                when="ansible_os_family == 'Debian'",
            )
            p.file(
                path=REMOTE_OUTPUT_DIR,
                state="directory",
                task_name="Create output directory",
            )
            # explicit ifnames has been given
            for session, ifname in self._tmux_sessions_maps:
                p.shell(
                    bg_start(
                        session,
                        (
                            f"tcpdump -w {REMOTE_OUTPUT_DIR}/{ifname}.pcap"
                            f" -i {ifname} {self.options}"
                        ),
                    ),
                    task_name=f"tcpdump for {ifname}",
                )
            p.debug(var="tcpdump_ifs")
            cmd = bg_start(
                "{{ item }}",
                "tcpdump -w %s/{{ item }}.pcap -i {{ item }} %s"
                % (REMOTE_OUTPUT_DIR, self.options),
            )
            # add some debug
            # p.debug(msg=cmd, loop="{{ tcpdump_ifs }}")
            p.shell(
                cmd, loop="{{ tcpdump_ifs }}", task_name="tcpdump on some interfaces"
            )

    def backup(self, backup_dir: Optional[Path] = None):
        _backup_dir = _set_dir(backup_dir, self.backup_dir)
        with play_on(roles=self.roles) as p:
            # zip the tcpdump directory
            p.shell(f"tar -czf tcpdump.tar.gz {REMOTE_OUTPUT_DIR}")
            p.fetch(src="tcpdump.tar.gz", dest=f"{str(_backup_dir)}")

    def destroy(self):
        with play_on(roles=self.roles) as p:
            for session, ifname in self._tmux_sessions_maps:
                p.shell(bg_stop(session), task_name=f"Stopping tcpdump on {ifname}")
            p.debug(var="tcpdump_ifs")
            p.shell(
                bg_stop("{{ item }}"),
                loop="{{ tcpdump_ifs }}",
                task_name="Stopping some tcpdumps",
            )
