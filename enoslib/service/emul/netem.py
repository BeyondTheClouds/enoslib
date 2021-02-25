import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Set, Tuple

from enoslib.api import play_on
from enoslib.objects import Host, Network
from enoslib.service.service import Service

from .utils import _build_commands, _build_options, _combine, _validate

logger = logging.getLogger(__name__)


class NetemConstraint(object):
    pass


@dataclass(eq=True, frozen=True)
class NetemOutConstraint(NetemConstraint):
    """A Constraint on the egress part of a device.

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
class NetemInConstraint(NetemOutConstraint):
    """A Constraint on the ingress part of a device.

    Inbound limitations works differently.
    see https://wiki.linuxfoundation.org/networking/netem

    We'll create an ifb, redirect incoming traffic to it and apply some
    queuing discipline using netem.

    Args:
        ifb: the ifb name (e.g. ifb0) that will be used. That means that the
             various ifbs must be provisionned out of band.
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
class NetemInOutSource(object):
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
        return [c for c in self.constraints if isinstance(c, NetemOutConstraint)]

    def add_constraints(self, constraints: Iterable[NetemInConstraint]):
        self.constraints = self.constraints.union(set(constraints))

    def add_commands(self) -> List[str]:
        return self._commands("add_commands")

    def remove_commands(self) -> List[str]:
        return self._commands("remove_commands")

    def commands(self) -> List[str]:
        return self._commands("commands")

    def all_commands(self) -> Tuple[List[str], List[str], List[str]]:
        return self.remove_commands(), self.add_commands(), self.commands()


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
    roles = dict(all=[htb_host.host for htb_host in sources])
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
            display_name="Applying the network constraints",
        )


class Netem(Service):
    def __init__(
        self,
        options: str,
        hosts: List[Host],
        networks: List[Network],
        symetric: bool = False,
        **kwargs,
    ):
        """Set homogeneous network constraints between your hosts.

        Geometricaly speaking: nodes are put on the vertices of a regular
        n-simplex.

        This calls :py:func:`enoslib.service.emul.netem.netem` function
        internally. As a consequence when symetric is True, it will apply 4
        times the constraints for bidirectionnal communication (out_a, in_b,
        out_b, in_a) and 2 times if symetric is False.

        Args:
            options   : raw netem options as described here:
                        http://man7.org/linux/man-pages/man8/tc-netem.8.html
            networks  : list of the networks to consider. Any interface with an
                        ip address on one of those network will be considered.
            hosts     : list of host on which the constraints will be applied
            symetric  : Wheter we'll want limitations on inbound and outbound traffic.
             kwargs   : keyword arguments to pass to :py:fun:`enoslib.api.run_ansible`

        Example:

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_netem.py
              :language: python
              :linenos:

        """
        self.options = options
        self.hosts = hosts if hosts else []
        self.networks = networks
        self.symetric = symetric
        self.kwargs = kwargs
        self.roles = dict(all=self.hosts)

    def deploy(self, chunk_size=100):
        """Apply the constraints on all the hosts."""
        # will hold the number of ifbs to provision
        total_ifbs = 1
        sources = []
        for host in self.hosts:
            interfaces = host.filter_interfaces(self.networks)
            source = NetemInOutSource(host)
            for idx, interface in enumerate(interfaces):
                constraints = []
                constraints.append(
                    NetemOutConstraint(device=interface, options=self.options)
                )
                if self.symetric:
                    constraints.append(
                        NetemInConstraint(
                            device=interface, options=self.options, ifb=f"ifb{idx}"
                        )
                    )
                source.add_constraints(constraints)
            total_ifbs = max(total_ifbs, len(interfaces))
            sources.append(source)
        netem(sources, self.extra_vars, chunk_size, **self.kwargs)

    def backup(self):
        pass

    def validate(self, output_dir=None):
        all_addresses = []
        for host in self.hosts:
            addresses = host.filter_addresses(self.networks)
            all_addresses.extend([str(addr.ip.ip) for addr in addresses])
        _validate(self.roles, output_dir, all_addresses, **self.kwargs)

    def destroy(self):
        # We need to know the exact device
        # all destroy all the rules on all the devices...
        pass
