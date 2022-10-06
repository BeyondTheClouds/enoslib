import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from enoslib.api import play_on, Results
from enoslib.constants import TMP_DIRNAME
from enoslib.html import (
    convert_list_to_html_table,
    html_from_sections,
    html_to_foldable_section,
    repr_html_check,
)
from enoslib.objects import Host, Network, PathLike, Roles
from enoslib.service.emul.objects import BaseNetem

from .utils import _build_commands, _build_options, _combine, _destroy, _validate

logger = logging.getLogger(__name__)


@dataclass(eq=True, frozen=True)
class NetemConstraint:
    device: str
    options: str


class NetemOutConstraint(NetemConstraint):
    """A Constraint on the egress part of a device.

    Args:
        device: the device name where the qdisc will be added
        options: the options string the pass down to netem (e.g. delay 10ms)
    """

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
class NetemInConstraint(NetemOutConstraint):
    """A Constraint on the ingress part of a device.

    Inbound limitations works differently.
    see https://wiki.linuxfoundation.org/networking/netem

    We'll create an ifb, redirect incoming traffic to it and apply some
    queuing discipline using netem.

    Args:
        ifb: the ifb name (e.g. ifb0) that will be used. That means that the
             various ifbs must be provisioned out of band.
    """

    def add_commands(self, ifb: str) -> List[str]:
        """Return the commands that adds the ifb."""
        return [
            f"tc qdisc add dev {self.device} ingress",
            f"ip link add {ifb} type ifb",
            f"ip link set dev {ifb} up",
        ]

    def remove_commands(self, ifb: str) -> List[str]:
        """Return the commands that remove the qdisc from the ifb and the net device."""
        return super().remove_commands(ifb) + [f"tc qdisc del dev {ifb} root"]

    def commands(self, ifb: str) -> List[str]:
        """Return the commands that redirect and apply netem constraints on the ifb."""
        return [
            (
                f"tc filter add dev {self.device} parent ffff: "
                "protocol ip u32 match u32 0 0 flowid 1:1 "
                f"action mirred egress redirect dev {ifb}"
            ),
            f"tc qdisc add dev {ifb} root netem {self.options}",
        ]


@dataclass
class NetemInOutSource:
    """Model a host and the constraints on its network devices.

    Args:
        inbound : The constraints to set on the ingress part of the host
                  devices
        outbound: The constraints to set on the egress part of the host
                  devices
    """

    host: Host
    constraints: Set[NetemConstraint] = field(default_factory=set)

    def _commands(self, _c: str) -> List[str]:
        cmds = []
        for idx, constraint in enumerate(self.constraints):
            cmds.extend(getattr(constraint, _c)(f"ifb{idx}"))
        return cmds

    @property
    def inbounds(self) -> List[NetemInConstraint]:
        return [c for c in self.constraints if isinstance(c, NetemInConstraint)]

    @property
    def outbounds(self) -> List[NetemOutConstraint]:
        # fixme subclassing smells here
        return [
            c
            for c in self.constraints
            if isinstance(c, NetemOutConstraint)
            and not isinstance(c, NetemInConstraint)
        ]

    def add_constraints(self, constraints: Iterable[NetemConstraint]):
        """Merge constraints to existing ones.

        In this context if two constraints are set on the same device we
        overwrite the original one.
        At the end we ensure that there's only one constraint per device

        Args:
            constraints: Iterable of NetemIn[Out]Constraint
        """
        for constraint in constraints:
            matched = [sc for sc in self.constraints if self.equal(constraint, sc)]
            for c in matched:
                self.constraints.discard(c)
            self.constraints.add(constraint)

    def equal(self, c1: NetemConstraint, c2: NetemConstraint):
        """Encode the equality between two constraints in this context."""
        return c1.__class__ == c2.__class__ and c1.device == c2.device

    def add_commands(self) -> List[str]:
        return self._commands("add_commands")

    def remove_commands(self) -> List[str]:
        return self._commands("remove_commands")

    def commands(self) -> List[str]:
        return self._commands("commands")

    def all_commands(self) -> Tuple[List[str], List[str], List[str]]:
        return self.remove_commands(), self.add_commands(), self.commands()

    @repr_html_check
    def _repr_html_(self, content_only=False):
        inbounds = [
            dict(device=c.device, direction="in", options=c.options)
            for c in self.inbounds
        ]
        outbounds = [
            dict(device=c.device, direction="out", options=c.options)
            for c in self.outbounds
        ]
        return html_from_sections(
            str(self.__class__),
            convert_list_to_html_table(inbounds + outbounds),
            content_only=content_only,
        )


def netem(sources: List[NetemInOutSource], chunk_size: int = 100, **kwargs):
    """Helper function to enforce in/out limitations on host devices.

    Nodes can be seen as the vertices of a star topology where the center is the
    core of the network. For instance the higher the latency on a node is, the
    further it is from the core of the network.

    This method is optimized toward execution time: enforcing thousands of
    atomic constraints (= tc commands) shouldn't be a problem. Commands are
    sent by batch and ``chunk_size`` controls the size of the batch.

    Idempotency note: the existing qdiscs are removed before applying new
    ones. This must be safe in most of the cases to consider that this is a
    form of idempotency.

    Args:
        sources: list of constraints to apply as a list of Source
        chunk_size: size of the chunk to use
        kwargs: keyword argument to pass to  :py:fun:`enoslib.api.run_ansible`.


    Example:

        .. literalinclude:: ../tutorials/network_emulation/tuto_netem.py
            :language: python
            :linenos:
    """

    # provision a sufficient number of ifbs
    roles = Roles(all=[htb_host.host for htb_host in sources])
    tc_commands = _combine(*_build_commands(sources), chunk_size=chunk_size)
    extra_vars = kwargs.pop("extra_vars", {})
    options = _build_options(extra_vars, {"tc_commands": tc_commands})

    # Run the commands on the remote hosts (only those involved)
    # First allocate a sufficient number of ifbs
    with play_on(roles=roles, gather_facts=False, extra_vars=options, **kwargs) as p:
        p.raw(
            "{{ item }}",
            when="tc_commands[inventory_hostname] is defined",
            loop="{{ tc_commands[inventory_hostname] }}",
            task_name="Applying the network constraints",
        )


class Netem(BaseNetem):
    def __init__(
        self,
    ):
        """Set homogeneous network constraints on some hosts

        Geometrically speaking: nodes are put on a star topology.
        Limitation are set from a node to/from the center of the Network.

        This calls :py:func:`~enoslib.service.emul.netem.netem` function
        internally. As a consequence when symmetric is True, it will apply 4
        times the constraints for bidirectional communication (out_a, in_b,
        out_b, in_a) and 2 times if symmetric is False.

        Example:

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_netem.py
              :language: python
              :linenos:

        - Using a secondary network.

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_netem_s.py
              :language: python
              :linenos:
        """
        self.sources = {}

    def add_constraints(
        self,
        options: str,
        hosts: Iterable[Host],
        symmetric: bool = False,
        networks: Optional[Iterable[Network]] = None,
        *,
        symetric: bool = None,
    ):
        if symetric is not None:  # Remove when deprecation phase will be ended
            symmetric = symetric
            import warnings

            warnings.warn(
                "symetric is deprecated; use symmetric", DeprecationWarning, 2
            )
        for src_host in hosts:
            self.sources.setdefault(src_host, NetemInOutSource(src_host))
            source = self.sources[src_host]
            interfaces = src_host.filter_interfaces(networks)
            for interface in interfaces:
                constraints = [NetemOutConstraint(device=interface, options=options)]
                if symmetric:
                    constraints.append(
                        NetemInConstraint(device=interface, options=options)
                    )
                source.add_constraints(constraints)
        return self

    def deploy(self, chunk_size=100, **kwargs):
        """Apply the constraints on all the hosts."""
        netem(list(self.sources.values()), chunk_size, **kwargs)

    def backup(self):
        pass

    def validate(
        self, networks: Iterable[Network] = None, output_dir: PathLike = None, **kwargs
    ) -> Results:
        if output_dir is None:
            output_dir = Path.cwd() / TMP_DIRNAME
        return _validate(
            list(self.sources.keys()),
            networks=networks,
            output_dir=output_dir,
            **kwargs,
        )

    def destroy(self, **kwargs):
        _destroy(list(self.sources.keys()), **kwargs)

    @repr_html_check
    def _repr_html_(self, content_only=False):
        sections = [
            html_to_foldable_section(h.alias, s._repr_html_(content_only=True))
            for h, s in self.sources.items()
        ]
        return html_from_sections(
            str(self.__class__), sections, content_only=content_only
        )
