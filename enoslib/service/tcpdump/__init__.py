from pathlib import Path
from typing import List, Optional, Union


from enoslib.api import play_on
from enoslib.objects import Host, Network
from ..service import Service


REMOTE_OUTPUT_DIR = "/tmp/__enoslib_tcpdump__"
LOCAL_OUTPUT_DIR = "__enoslib_tcpdump__"


def bg(key: str, cmd: str) -> str:
    """Put a command in the backgound.

    Generate the command that will put cmd in background.
    This uses tmux to detach cmd from the current shell session.

    Idempotent

    Args:
        key: session identifier for tmux (must be unique)
        cmd: the command to put in background

    Returns:
        cmd encapsulated in a tmux session

    """
    # supports templating
    return "(tmux ls | grep %s) ||tmux new-session -s %s -d '%s'" % (key, key, cmd)


class TCPDump(Service):
    def __init__(
        self,
        hosts: List[Host],
        ifnames: Optional[List[str]] = None,
        networks: Optional[List[Network]] = None,
        backup_dir: Union[Path, str] = Path(LOCAL_OUTPUT_DIR),
    ):
        """Monitor network traffic using tcpdump.

        This connects to every hosts to launch as many tcpdump processes as
        network interfaces to monitor.  The pcap files can be retrieved and
        analysed by your favorite tool (wireshark, scappy ...).  Each tcpdump
        process is launched in the background using a dedicted tmux session.

        Can be used as a Context Manager. In this case, the pcap files are
        retrieved automatically when exiting and all the remaining tcpdump
        processes are killed.

        Note that if networks is used, :py:func:`~enoslib.api.sync_info` must
        have been called before.

        Args:
            hosts: list of hosts to consider
            ifnames: explicit network card names to monitor
            networks: monitor all interfaces that belong to one of those networks
            backup_dir: path to a local directory where the pcap files will be saved

        Examples:

            .. literalinclude:: examples/tcpdump.py
                    :language: python
                    :linenos:
        """
        self.hosts = hosts
        self.ifnames = ifnames if ifnames else []
        self.networks = networks if networks else []
        self.roles = dict(all=hosts)
        self._tmux_sessions_maps = [(s, s) for s in self.ifnames]
        self.backup_dir = Path(backup_dir)

        # handle networks
        for host in hosts:
            ifs = host.filter_interfaces(self.networks)
            host.extra.update(tcpdump_ifs=ifs)

    def deploy(self, force=False):
        # get rid of existing sessions
        if force:
            self.destroy()
        with play_on(roles=self.roles) as p:
            p.apt(name=["tcpdump", "tmux"], state="present")
            p.file(path=REMOTE_OUTPUT_DIR, state="directory")
            # explicit ifnames has been given
            for session, ifname in self._tmux_sessions_maps:
                p.shell(
                    bg(
                        session,
                        f"tcpdump -i {ifname} -w {REMOTE_OUTPUT_DIR}/{ifname}.pcap",
                    )
                )
            p.debug(var="tcpdump_ifs")
            p.shell(
                bg(
                    "{{ item }}",
                    "tcpdump -i {{ item }} -w %s/{{ item }}.pcap" % REMOTE_OUTPUT_DIR,
                ),
                loop="{{ tcpdump_ifs }}",
            )

    def backup(self):
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
        with play_on(roles=self.roles) as p:
            # zip the tcpdump directory
            p.shell(f"tar -czf tcpdump.tar.gz {REMOTE_OUTPUT_DIR}")
            p.fetch(src="tcpdump.tar.gz", dest=f"{str(self.backup_dir)}")

    def destroy(self):
        with play_on(roles=self.roles) as p:
            for session, _ in self._tmux_sessions_maps:
                p.shell(f"tmux kill-session -t {session} || true")
            p.debug(var="tcpdump_ifs")
            p.shell("tmux kill-session -t {{ item }} || true", loop="{{ tcpdump_ifs }}")

    def __enter__(self):
        self.deploy(force=True)

    def __exit__(self, *args):
        self.backup()
        self.destroy()
