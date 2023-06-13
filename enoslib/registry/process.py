import logging
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from enoslib.api import (
    _enoslib_cgroup,
    actions,
    cg_list,
    cg_status,
    cg_stop,
    run_command,
)
from enoslib.config import config_context
from enoslib.html import (
    convert_dict_to_html_table,
    convert_list_to_html_table,
    html_from_sections,
    html_to_foldable_section,
    repr_html_check,
)
from enoslib.log import DisableLogging
from enoslib.objects import Host, Roles, RolesLike
from enoslib.utils import _hostslike_to_roles

from .utils import State, check_args, check_cron_date

logger = logging.getLogger(__name__)


class ProcessGroup:
    def __init__(self, group: str, host: Host, state: State = State.ALIVE) -> None:
        self.group = group
        self.host = host
        self.state = state

    def __str__(self) -> str:
        """
        Returns a string format representation of a process.
        """
        return f"({self.group}, {self.host.address}," f"{self.state.name})\n"

    def __eq__(self, other: object) -> bool:
        """
        Overloading the default == operator.

        Two processes are equal if :
            - they have the same name
            - they are running on the same node
        """
        if not isinstance(other, ProcessGroup):
            return NotImplemented
        if self.group == other.group and self.host == other.host:
            return True
        return False

    @repr_html_check
    def _repr_html_(self, content_only: bool = False) -> str:
        d = dict(Name=self.group, State=self.state.name)
        return convert_dict_to_html_table(d)

    def kill(self, signum: int = signal.SIGINT) -> None:
        """
        Kills a process group synchronously.

        Can be personalized :
            - the signal
        """
        check_args(signum=signum)
        if self.isalive():
            run_command(
                cg_stop(self.group),
                task_name=f"Killing process group with name {self.group}",
                roles=self.host,
                gather_facts=False,
                on_error_continue=True,
            )
        else:
            logger.error(
                f"kill() not executed - Process with name {self.group} is already dead"
            )

    def kill_async(
        self,
        signum: int = signal.SIGINT,
        start_at: Optional[datetime] = None,
        start_in: Optional[timedelta] = None,
    ) -> None:
        """
        Kills a process asynchronously.
        Based on cron, a job scheduler on Unix-like operating systems.

        Args:
            signum : the signal constant to send with the kill
            start_at : a datetime.datetime object to specify an exact date (>now+1min)
            start_in : a datetime.timedelta object to specify a delay (>1min)

        If both time arguments are specified, the priority is given to
        the datetime.datetime object, start_at.
        """
        check_args(
            signum=signum,
            start_at=start_at,
            start_in=start_in,
            is_async=True,
        )

        if start_at is not None:
            date = start_at
        elif start_in is not None:
            date = datetime.now() + start_in

        check_cron_date(date=date)

        with actions(roles=self.host) as p:
            p.cron(
                name=f"Setting up cron to kill process with name {self.group}"
                f" at {str(date)}",
                minute=date.minute,
                hour=date.hour,
                day=date.day,
                month=date.month,
                weekday=date.weekday(),
                job=f"sleep {date.second} && {cg_stop(self.group)}",
            )

    def refresh(self) -> None:
        """Refresh the state of the process group."""
        with DisableLogging(level=logging.ERROR):
            with config_context(ansible_stdout="noop"):
                r = run_command(
                    cg_status(self.group),
                    roles=self.host,
                    gather_facts=False,
                    on_error_continue=True,
                )
        if r[0].rc != 0:
            self.set_dead()
        else:
            self.set_alive()

    def isalive(self) -> bool:
        """
        Check if a process is alive.
        """
        return self.state == State.ALIVE

    def set_alive(self, pid: Optional[str] = None) -> None:
        """
        Set a process to State.ALIVE.
        """
        self.state = State.ALIVE

    def set_dead(self) -> None:
        """
        Set a process to State.DEAD.
        """
        self.state = State.DEAD


def _build_hosts_with_extra(processes: List[ProcessGroup]) -> List[Host]:
    hosts = set()
    for p in processes:
        p.host.set_extra(cgroups=[])
        hosts.add(p.host)
    for p in processes:
        extra = p.host.get_extra()
        extra.setdefault("cgroups", [])
        cgroups = extra["cgroups"]
        cgroups.append(p.group)
        p.host.set_extra(cgroups=cgroups)

    return list(hosts)


class ProcessRegistry:
    def __init__(
        self,
        processes: Optional[List[ProcessGroup]] = None,
        glob: str = "*",
        roles: Optional[RolesLike] = None,
    ) -> None:
        self.processes: List[ProcessGroup] = processes if processes else []
        self.glob = glob
        self.roles = roles if roles else None
        # computed
        self.size = 0

    def __str__(self) -> str:
        """
        Returns a string format representation of a Process Registry.
        """
        string = f"Registry of size {self.size} build with regexp = {self.glob} :\n[\n"
        for p in self.processes:
            string += str(p)
        string += "]\n"

        return string

    def __eq__(self, other: object) -> bool:
        """
        Overloading the default == operator.

        Two registries are equals if all of their attributes are equals.
        """
        if not isinstance(other, ProcessRegistry):
            return NotImplemented
        if (
            self.processes == other.processes
            and self.glob == other.glob
            and self.roles == other.roles
            and self.size == other.size
        ):
            return True
        return False

    @repr_html_check
    def _repr_html_(self, content_only: bool = False) -> str:
        repr_title = f"{str(self.__class__)}@{hex(id(self))}"
        contents: Dict[Host, List] = {}
        for p in self.processes:
            p_to_dict = dict(
                Name=p.group,
                State=p.state,
            )
            if contents.get(p.host) is not None:
                contents[p.host].append(p_to_dict)
            else:
                contents[p.host] = [p_to_dict]

        host_contents: List[str] = []
        for host, plist in contents.items():
            host_contents.append(
                html_to_foldable_section(
                    str(host.alias),
                    convert_list_to_html_table(plist),
                    extra=str(len(plist)),
                )
            )
        return html_from_sections(repr_title, host_contents, content_only=content_only)

    def append(self, p: Union[ProcessGroup, List[ProcessGroup]]) -> None:
        """
        Add a process or a list of processes to the registry.
        """
        if isinstance(p, ProcessGroup):
            self.processes.append(p)
            self.size += 1
        else:
            self.processes += p
            self.size += len(p)

    def refresh(self) -> "ProcessRegistry":
        """
        Returns an updated version of the registry
        based on self's specifications.
        """
        # contain only alive processes for now
        if self.roles is None:
            return ProcessRegistry([], self.glob, None)
        refreshed_registry = ProcessRegistry.build(self.glob, self.roles)

        alive_processes = refreshed_registry.processes

        # if in self.processes but not in the refreshed one,
        # than the process is dead
        for p in self.processes:
            if p not in alive_processes:
                p.set_dead()
                refreshed_registry.append(p)

        return refreshed_registry

    def lookup(self, hosts: List[Host]) -> "ProcessRegistry":
        """
        Returns a sub-registry with processes that runs on the specified hosts.
        """

        registry = ProcessRegistry()
        registry.glob = self.glob
        registry.roles = hosts
        for h in hosts:
            plist = [p for p in self.processes if p.host == h]
            registry.append(plist)

        registry.size = len(registry.processes)

        return registry

    @classmethod
    def build(cls, glob: str, roles: RolesLike) -> "ProcessRegistry":
        """
        Build a registry with processes which have a command
        that correspond to a glob on roles.
        """
        _roles = _hostslike_to_roles(roles)

        assert _roles is not None
        processes = []
        # retreive all processes following a regexp and format
        # the ouput such that we obtain the pid, the command and the name
        # with DisableLogging(level=logging.ERROR):
        #    with config_context(ansible_stdout="noop"):
        results = run_command(
            cg_list(glob),
            task_name=f"Building registry with regexp : {glob}",
            roles=roles,
            gather_facts=False,
            on_error_continue=True,
            raw=True,  # allow to use shell expansion
        )
        for r in results:
            # r has the following format:
            #
            # path1 (e.g /sys/fs/cgroup/__enoslib__foo)
            # #
            # pid11
            # pid12
            # ##
            # path2
            # #
            # pid21
            # pid22
            # ...
            # one result per host
            if r.status == "FAILED" or r.rc != 0 or r.stdout == "":
                continue
            cgroups = r.stdout.split("##")
            for cgroup in cgroups:
                _cgroup = cgroup.strip()
                if not _cgroup:
                    continue
                if "#" not in _cgroup:
                    continue
                path, pids = _cgroup.split("#")
                path = path.strip()
                pids = pids.strip()
                # recover the logical name
                group = Path(path).stem.replace(_enoslib_cgroup(""), "")
                address = r.host
                # find the host back
                for key in _roles.keys():
                    for item in _roles[key]:
                        if address == item.address:
                            host = item
                            break
                # set to alive by default
                s = State.DEAD
                if pids:
                    s = State.ALIVE
                processes.append(ProcessGroup(group, host, s))

        return cls(processes, glob, _roles)

    def kill(self, signum: int = signal.SIGINT) -> None:
        """
        Kills all registered processes synchronously.

        Args:
            signum : the signal constant to send with the kills
        """
        check_args(signum=signum)

        hosts = _build_hosts_with_extra(self.processes)
        run_command(
            cg_stop("{{ item }}"),
            task_name="Killing all processes",
            roles=list(hosts),
            gather_facts=False,
            on_error_continue=True,
            loop="{{ cgroups }}",
        )

    def kill_incr(
        self,
        signum: int = signal.SIGINT,
        number: int = sys.maxsize,
        interval: timedelta = timedelta(seconds=0),
    ) -> None:
        """
        Kills incrementally, randomly and synchronously n process(es).

        Args:
            signum : the signal constant to send with the kills
            number : the number of processes to kill (>0)
            interval : a datetime.timedelta object to specify the time
                       between the kills (>=0sec)
        """
        check_args(
            signum=signum,
            number=number,
            interval=interval,
        )

        alive_registry = self.get_alive_processes()
        _processes = [p for p in alive_registry.processes]

        _nkill = min(number, len(_processes))

        for _n in range(_nkill):
            _p = random.choice(_processes)
            _p.kill(signum)

            _index = _processes.index(_p)
            _processes.pop(_index)

            if _n != _nkill - 1:
                time.sleep(interval.total_seconds())

    def kill_async(
        self,
        signum: int = signal.SIGINT,
        start_at: Optional[datetime] = None,
        start_in: Optional[timedelta] = timedelta(seconds=120),
    ) -> None:
        """
        A method that kills all processes asynchronously.
        Based on cron, a job scheduler on Unix-like operating systems.

        Args:
            signum : the signal constant to send with the kills
            start_at : a datetime.datetime object to specify an exact date (>now+1min)
            start_in : a datetime.timedelta object to specify a delay (>1min)

        If both time arguments are specified, the priority is given to
        the datetime.datetime object, start_at.
        """
        check_args(
            signum=signum,
            start_at=start_at,
            start_in=start_in,
            is_async=True,
        )
        if start_at is not None:
            date = start_at
        elif start_in is not None:
            date = datetime.now() + start_in

        check_cron_date(date=date)

        hosts = _build_hosts_with_extra(self.processes)
        with actions(roles=hosts) as p:
            p.cron(
                name="Setting up cron to kill process group {{ item }} "
                f"at {str(date)}",
                minute=date.minute,
                hour=date.hour,
                day=date.day,
                month=date.month,
                weekday=date.weekday(),
                job=f"sleep {date.second} && {cg_stop('{{ item }}')}",
                loop="{{ cgroups }}",
            )

    def kill_async_incr(
        self,
        signum: int = signal.SIGINT,
        number: int = sys.maxsize,
        start_at: Optional[datetime] = None,
        start_in: Optional[timedelta] = None,
        interval: timedelta = timedelta(seconds=0),
    ) -> None:
        """
        Kills incrementally, randomly and asynchronously n process(es).

        Args:
            signum : the signal constant to send with the kills
            number : the number of processes to kill (>0)
            start_at : a datetime.datetime object to specify an exact date (>now+1min)
            start_in : a datetime.timedelta object to specify a delay (>1min)
            interval : a datetime.timedelta object to specify the time
                       between the kills (>=0sec)

        If both time arguments are specified, the priority is given to
        the datetime.datetime object, start_at.
        """
        check_args(
            signum=signum,
            start_at=start_at,
            start_in=start_in,
            number=number,
            interval=interval,
            is_async=True,
        )
        if start_at is not None:
            date = start_at
        elif start_in is not None:
            date = datetime.now() + start_in

        check_cron_date(date=date)

        alive_registry = self.get_alive_processes()
        _processes = [p for p in alive_registry.processes]

        _nkill = min(number, len(_processes))
        for _n in range(_nkill):
            _p = random.choice(_processes)
            _p.kill_async(signum, date + (_n * interval))

            _index = _processes.index(_p)
            _processes.pop(_index)

    def get_dead_processes(self) -> "ProcessRegistry":
        """
        Build a registry that contains only the processes
        set to State.DEAD.
        """
        dead_processes: ProcessRegistry = ProcessRegistry()

        dead_processes.glob = self.glob
        dead_processes.processes = [p for p in self.processes if p.state == State.DEAD]
        dead_processes.size = len(dead_processes.processes)

        dead_processes_hosts: List[Host] = []
        for p in dead_processes.processes:
            dead_processes_hosts.append(p.host)

        dead_processes.roles = Roles(all=dead_processes_hosts)

        return dead_processes

    def get_alive_processes(self) -> "ProcessRegistry":
        """
        Build a registry that contains only the processes
        set to State.ALIVE.
        """
        alive_processes: ProcessRegistry = ProcessRegistry()

        alive_processes.glob = self.glob
        alive_processes.processes = [
            p for p in self.processes if p.state == State.ALIVE
        ]
        alive_processes.size = len(alive_processes.processes)

        alive_processes_hosts: List[Host] = []
        for p in alive_processes.processes:
            alive_processes_hosts.append(p.host)

        alive_processes.roles = Roles(all=alive_processes_hosts)

        return alive_processes

    def set_dead(self) -> None:
        """
        Set all registered processes to State.DEAD.
        """
        for p in self.processes:
            p.set_dead()

    def set_alive(self) -> None:
        """
        Set all registered processes to State.ALIVE.
        """
        for p in self.processes:
            p.set_alive()

    def get(self, index: int):
        return self.processes[index % self.size]
