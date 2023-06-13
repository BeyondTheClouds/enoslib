import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Type, Union

from enoslib.api import actions, cg_start, cg_stop, cg_write
from enoslib.html import convert_list_to_html_table, html_from_dict, html_from_sections
from enoslib.objects import Host
from enoslib.registry.process import ProcessRegistry
from enoslib.registry.utils import check_cron_cmd

from ..service import Service

logger = logging.getLogger(__name__)


class Event:
    """
    Base class of an Event.

    An Event is tight to a date and a single host.

    Args:
        date: the date of the event
        host: the host on which the event will occur
        name: the name of the event
        cmd: command of the event
    """

    def __init__(self, date: datetime, host: Host, name: str, cmd: str = "") -> None:
        self.date = date
        self.host = host
        self.name = name
        self.cmd = cmd

    def to_dict(
        self,
    ) -> dict:
        """
        Convert an event to a dictionary.
        """
        date_dict = dict(
            second=self.date.second,
            minute=self.date.minute,
            hour=self.date.hour,
            day=self.date.day,
            month=self.date.month,
            weekday=self.date.weekday(),
        )
        d = dict(
            date=date_dict,
            name=self.name,
            cmd=self.cmd,
        )
        return d

    def repr_cmd(self):
        return self.cmd

    def to_repr_dict(self):
        d = self.to_dict()
        d["date"] = self.date
        d["cmd"] = self.repr_cmd()
        d["host"] = self.host.alias
        d["type"] = self.__class__.__name__
        return d

    def _repr_html_(self, content_only: bool = False) -> str:
        d = self.to_repr_dict()
        return html_from_dict(self.__class__.__name__, d, content_only=content_only)


class KillEvent(Event):
    """Kill a Group of process.

    Process in the cgroup "name" will be killed

    Args:
        date: date of the event
        host: host on which the event will occur
        name: process group to kill
    """

    def __init__(
        self,
        date: datetime,
        host: Host,
        name: str,
    ) -> None:
        super().__init__(date, host, name)
        self.cmd = cg_stop(name)

    def repr_cmd(self):
        return ""


class StartEvent(Event):
    """Start a Process and assign a it to a group.

    Args:
        date: date of the event
        host: host on which the event will occur
        cmd: command to lauch
        name: name of the process group in which cmd will be run
    """

    def __init__(self, *, date: datetime, host: Host, cmd: str, name: str) -> None:
        super().__init__(date, host, name)
        self._cmd = cmd
        self.cmd = cg_start(cmd, name)

    def repr_cmd(self):
        return self._cmd


class CGroupEvent(Event):
    """Set value for a cgroup controller."""

    def __init__(
        self, *, date: datetime, host: Host, name: str, cpath: str, value: str
    ) -> None:
        super().__init__(date, host, name)
        self.cpath = cpath
        self.value = value
        self.cmd = cg_write(name, cpath, value)

    def repr_cmd(self):
        return f"{self.cpath} = {self.value}"


class Planning:
    def __init__(
        self,
    ) -> None:
        self.events: List[Event] = []

    @property
    def duration(self):
        events = sorted(self.events, key=lambda e: e.date)
        return events[-1].date - events[0].date

    @property
    def start(self):
        events = sorted(self.events, key=lambda e: e.date)
        return events[0].date

    @property
    def end(self):
        events = sorted(self.events, key=lambda e: e.date)
        return events[-1].date

    @property
    def until_end(self):
        return self.end - datetime.now()

    def _repr_html_(self, content_only: bool = False) -> str:
        #
        sections = [e.to_repr_dict() for e in sorted(self.events, key=lambda e: e.date)]
        return html_from_sections(
            self.__class__.__name__,
            convert_list_to_html_table(sections),
            content_only=content_only,
        )

    def add_event(
        self,
        event: Event,
    ) -> "Planning":
        self.events.append(event)
        return self

    def to_dict(self) -> Dict[Host, List[Event]]:
        """
        Convert a planning to a dictionary.

        For a given host h, dict[h] will return
        all the event that will happen on h.
        """
        d: Dict[Host, List[Event]] = {}
        for event in self.events:
            if d.get(event.host) is not None:
                d[event.host].append(event)
            else:
                d[event.host] = [event]
        return d

    def check(self) -> None:
        """
        Verify the timeline of a planning based.
        """

        # for key,value as k,v
        # v represent all the event types that can happen right before k
        transition: Dict[Type[Event], Tuple[Union[None, Type[Event]], ...]] = {
            StartEvent: (None, KillEvent),
            KillEvent: (StartEvent,),
        }
        checked_ps: List[Tuple[str, Host]] = []
        for event in self.events:
            ns = event.name
            host = event.host

            ps = (ns, host)
            if ps not in checked_ps:
                checked_ps.append(ps)

                # extract all event(s) related to a namespace
                # and sort them chronologically
                ns_list = [
                    event
                    for event in self.events
                    if event.name == ns and event.host == host
                ]
                ns_list.sort(key=lambda event: event.date)

                # Verify first event
                if None not in transition[ns_list[0].__class__]:
                    raise Exception(
                        f"An error may occur with {event.name}, "
                        "the first scheduled event may not be allowed."
                    )

                # Verify all the others event(s) if any
                for n, event in enumerate(ns_list[1:], start=1):
                    if ns_list[n - 1].__class__ not in transition[event.__class__]:
                        raise Exception(
                            f"An error may occur with {event.name}, "
                            "please check the timeline of its event(s).\n"
                            f"An event of type {event.__class__} can't come after "
                            f"an event of type {ns_list[n - 1].__class__}."
                        )


class PlanningService(Service):
    """Execute and control processes according to a planning.

    Scheduling of events use cronjobs on each of the target nodes.

    Args:
        planning: optional.
            The planning to use
    """

    def __init__(self, planning: Optional[Planning] = None) -> None:
        self.planning = planning if planning is not None else Planning()

    def add_event(self, e: Event) -> "PlanningService":
        """Schedule an event.

        Args:
            e: the event to schedule

        Returns:
            The current PlanningService
        """
        self.planning.add_event(e)
        return self

    def _build_hosts_cmds(self) -> List[Host]:
        """Inject all the cron command descriptor in the host extra vars."""
        hosts: List[Host] = []

        for event in self.planning.events:
            event_dict = event.to_dict()

            check_cron_cmd(cmd=event_dict["cmd"])

            if event.host in hosts:
                _index = hosts.index(event.host)
                hosts[_index].extra["cmds"].append(event_dict)
            else:
                hosts.append(event.host)
                # cleanning to have at the end only the current cmds
                hosts[-1].reset_extra()
                hosts[-1].extra["cmds"] = [event_dict]

        return hosts

    def deploy(self) -> None:
        """
        Set all events / cronjobs of a planning.
        """
        hosts = self._build_hosts_cmds()
        with actions(roles=hosts) as p:
            p.cron(
                name="Running specified command for {{item.name}} at {{item.date}}",
                minute="{{item.date.minute}}",
                hour="{{item.date.hour}}",
                day="{{item.date.day}}",
                month="{{item.date.month}}",
                weekday="{{item.date.weekday}}",
                job="sleep {{item.date.second}} && {{item.cmd}}",
                loop="{{ cmds }}",
                state="present",
            )

    def destroy(self, wait: bool = True) -> None:
        """
        Remove all events / cronjobs of a planning.
        """
        # first remove all crons
        hosts = self._build_hosts_cmds()
        with actions(roles=hosts) as p:
            p.cron(
                name="Running specified command for {{ item.name }} at {{ item.date }}",
                loop="{{ cmds }}",
                state="absent",
            )

        # then build the status registry and kill the registry
        registry = self.status()
        if wait:
            registry.kill()
        else:
            registry.kill_async()

    def status(self) -> ProcessRegistry:
        """Status of the processes in the Planning"""
        names = {e.name for e in self.planning.events}
        hosts = {e.host for e in self.planning.events}
        if len(names) > 1:
            # use shell expansion to get the list of possible cgroup
            names_str = ",".join(names)
            names_str = f"{{{names_str}}}"
        elif len(names) == 1:
            names_str = names.pop()
        else:
            return ProcessRegistry()
        r = ProcessRegistry.build(f"{names_str}", roles=hosts)
        return r

    def check(self) -> None:
        """Check for inconsistencies in the planning"""
        self.planning.check()

    @property
    def duration(self) -> timedelta:
        """The timespan as a timedelta of the planning."""
        return self.planning.duration

    @property
    def start(self) -> datetime:
        """Date as a datetime of the first event."""
        return self.planning.start

    @property
    def end(self) -> datetime:
        """Date as a datetime of the last event."""
        return self.planning.end

    @property
    def until_end(self) -> timedelta:
        """Duration between now and the last event of the planning."""
        return self.planning.until_end

    def backup(self) -> None:
        pass

    def _repr_html_(self) -> str:
        return self.planning._repr_html_()
