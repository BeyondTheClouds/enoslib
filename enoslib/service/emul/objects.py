from dataclasses import dataclass
from typing import Iterable, List
from enoslib.objects import Host


class Constraint(object):
    pass


@dataclass
class Source(object):
    """Base class for our limitations.

    Constraint are applied on a host so, keeping this as an attribute.

    Args:
        host: the host on which the constraint will be applied
    """

    host: Host

    def add_constraints(self, constraints: Iterable[Constraint]):
        """Subclass specific, because that depends how constraints can be combined."""
        pass

    def all_commands(self):
        """all in one."""
        r = self.remove_commands()
        a = self.add_commands()
        h = self.commands()
        return r, a, h
