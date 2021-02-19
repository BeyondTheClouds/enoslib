
from dataclasses import dataclass, field
from typing import List, Mapping, Optional

from enoslib.api import play_on
from .objects import Constraint, Source
from .utils import _build_commands, _build_options, _combine


@dataclass(eq=True, frozen=True)
class NetemInConstraint(Constraint):
    """Generic In Constraint.

    .. note ::

        https://wiki.linuxfoundation.org/networking/netem

    Args:
        device: the device name where the qdisc will be added
        options: the options string the pass down to netem (e.g delay 10ms)
    """

    device: str
    options: str

    def __post_init__(self):
        if not self.options:
            raise ValueError("options must be set")

    def add_commands(self, _: str) -> List[str]:
        return [f"tc qdisc add dev {self.device} root netem {self.options}"]

    def remove_commands(self, _: str) -> List[str]:
        return [f"tc qdisc del dev {self.device} root || true"]

    def commands(self, _: str) -> List[str]:
        """Nothing to do."""
        return []


@dataclass(eq=True, frozen=True)
class NetemOutConstraint(NetemInConstraint):
    """Handle inbound limitations.

    Inbound limitations works differently.
    Quoted from https://wiki.linuxfoundation.org/networking/netem

    > How can I use netem on incoming traffic?

    > You need to use the Intermediate Functional Block pseudo-device IFB .
      This network device allows attaching queuing discplines to incoming
      packets.

    .. code-block:: bash

        modprobe ifb
        ip link set dev ifb0 up
        tc qdisc add dev eth0 ingress
        tc filter add dev eth0 parent ffff: \
        protocol ip u32 match u32 0 0 flowid 1:1 action mirred egress redirect dev ifb0
        tc qdisc add dev ifb0 root netem delay 750ms

    Assuming that the modprobe is already done this is exactly what we'll do
    to enforce the inbound constraints.

    Args:
        ifb: the ifb name (e.g. ifb0) that will be used. That means that the
             various ifbs must be provisionned out of band.
    """
    def add_commands(self, ifb: str) -> List[str]:
        return [f"ip link set dev {ifb} up", f"tc qdisc add dev {self.device} ingress"]

    def remove_commands(self, ifb: str) -> List[str]:
        return super().remove_commands(ifb) + [f"tc qdisc del dev {ifb} root"]

    def commands(self, ifb: str) -> List[str]:
        return [
            f"tc filter add dev {self.device} parent ffff: protocol ip u32 match u32 0 0 flowid 1:1 action mirred egress redirect dev {ifb}",
            f"tc qdisc add dev {ifb} root netem {self.options}",
        ]


@dataclass
class NetemInOutSource(Source):
    inbounds: List[NetemInConstraint] = field(default_factory=list)
    outbounds: List[NetemOutConstraint] = field(default_factory=list)

    def _commands(self, _c: str) -> List[str]:
        cmds = []
        for xgress in [self.inbounds, self.outbounds]:
            for idx, constraint in enumerate(xgress):
                cmds.extend(getattr(constraint, _c)(f"ifb{idx}"))
        return cmds

    def add_commands(self) -> List[str]:
        return self._commands("add_commands")

    def remove_commands(self) -> List[str]:
        return self._commands("remove_commands")

    def commands(self) -> List[str]:
        return self._commands("commands")

    def add_constraints(self, constraints: List[NetemInConstraint]):
        if len(constraints) == 0 or len(constraints) > 2:
            raise ValueError("One or two constraints must be passed")
        self.inbounds.append(constraints[0])
        if len(constraints) == 2:
            self.outbounds.append(constraints[1])


def netem(
    sources: List[NetemInOutSource],
    extra_vars: Optional[Mapping] = None,
    chunk_size: int = 100,
):
    """Helper function to enforce heteregeneous in/out limitations on nodes

    Geometricaly speaking: the nodes are put on the vertices of a n-simplex
    (non regular in the general case)

    This method is optimized toward execution time: enforcing thousands of
    atomic constraints (= tc commands) shouldn't be a problem. Commands are
    sent by batch and ``chunk_size`` controls the size of the batch.

    Idempotency note: the existing qdiscs are removed before applying new
    ones. This must be safe in most of the cases to consider that this is a
    form of idempotency.

    Args:
        sources: list of constraints to apply as a list of Source
        extra_vars: extra variable to pass to Ansible when enforcing the constraints
        chunk_size: size of the chunk to use
    """
    if extra_vars is None:
        extra_vars = dict()

    # provision a sufficient number of ifbs
    roles = dict(all=[htb_host.host for htb_host in sources])
    tc_commands = _combine(*_build_commands(sources), chunk_size=chunk_size)
    options = _build_options(extra_vars, {"tc_commands": tc_commands})

    # find out how many ifbs we'll have to provision
    # by default modprobe provision 2, so we default to this value
    numifbs = 2
    for source in sources:
        numifbs = max(numifbs, len(source.inbounds), len(source.outbounds))

    # Run the commands on the remote hosts (only those involved)
    # First allocate a sufficient number of ifbs
    with play_on(roles=roles, extra_vars=options) as p:
        p.raw(f"modprobe ifb numifbs={numifbs}")
        p.raw(
            "{{ item }}",
            when="tc_commands[inventory_hostname] is defined",
            loop="{{ tc_commands[inventory_hostname] }}",
            display_name="Applying the network constraints",
        )