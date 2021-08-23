"""HTB based emulation."""
import logging
import os
from dataclasses import dataclass, field
from itertools import product
from typing import Dict, Iterable, List, Optional, Set, Tuple

from enoslib.api import play_on
from enoslib.constants import TMP_DIRNAME
from enoslib.objects import Host, Network, Networks, Roles
from enoslib.service.emul.schema import HTBConcreteConstraintValidator, HTBValidator

from ..service import Service
from .utils import _build_commands, _build_options, _combine, _destroy, _validate

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
PLAYBOOK = os.path.join(SERVICE_PATH, "netem.yml")
TMP_DIR = os.path.join(os.getcwd(), TMP_DIRNAME)

DEFAULT_RATE = "10gbit"

DEFAULT_LOSS = 0


logger = logging.getLogger(__name__)


@dataclass(eq=True, frozen=True)
class HTBConstraint(object):
    """An HTB constraint.

    .. note ::

        Ref: https://tldp.org/HOWTO/Adv-Routing-HOWTO/lartc.qdisc.classful.html

    An HTBconstraint will be enforced by creating a filter and a class.
    The filtering stage will send the packet to the class (delay, rate and
    loss will be applied) based on the target ip.

    The purpose of this class is to give you the commands to create the slice
    (class and filter) that will be added to the root qdisc.

     Args:
        target: the target ip
        device: the device name where the qdisc will be added
        delay: the delay (e.g 10ms)
        rate: the rate (e.g 10gbit)
        loss: the loss (e.g "0.05" == "5%")
    """

    device: str
    delay: str
    target: str
    rate: str = DEFAULT_RATE
    loss: float = DEFAULT_LOSS

    def __post_init__(self):
        HTBConcreteConstraintValidator.validate(
            dict(device=self.device, target=self.target, rate=self.rate, loss=self.loss)
        )

    def add_commands(self) -> List[str]:
        """Add the classful qdisc at the root of the device."""
        return [f"tc qdisc add dev {self.device} root handle 1: htb"]

    def remove_commands(self) -> List[str]:
        """Remove everything."""
        return [f"tc qdisc del dev {self.device} root || true"]

    def commands(self, idx: int):
        """Get the command for the current slice."""
        cmds = []
        cmds.append(
            (
                f"tc class add dev {self.device} "
                "parent 1: "
                f"classid 1:{idx + 1} "
                f"htb rate {self.rate}"
            )
        )

        # could be 0 or None
        if not self.loss:
            cmd = (
                f"tc qdisc add dev {self.device} "
                f"parent 1:{idx + 1} "
                f"handle {idx + 10}: "
                f"netem delay {self.delay}"
            )
        else:
            cmd = (
                f"tc qdisc add dev {self.device} "
                f"parent 1:{idx + 1} "
                f"handle {idx + 10}: "
                f"netem delay {self.delay} "
                f"loss {self.loss}"
            )
        cmds.append(cmd)
        cmd = (
            f"tc filter add dev {self.device} "
            "parent 1: "
            f"protocol ip u32 match ip dst {self.target} "
            f"flowid 1:{idx + 1}"
        )
        cmds.append(cmd)
        return cmds


@dataclass
class HTBSource(object):
    """Model a host and all the htb constraints.

    Args
        host: Host where the constraint will be applied
        constaints: list of :py:class:`enoslib.service.netem.netem.HTBConstraint`

    .. note ::

        Consistency check (such as device names) between the host and the
        constraints are left to the application.
    """

    host: Host
    constraints: Set[HTBConstraint] = field(default_factory=set)

    def add_constraint(self, *args, **kwargs):
        """Add a constraint.

        *args and **kwargs are those from
        :py:class:`enoslib.service.netem.netem.HTBConstraint`
        """
        self.add_constraints([HTBConstraint(*args, **kwargs)])

    def add_constraints(self, constraints: Iterable[HTBConstraint]):
        """Merge constraints to existing ones.

        In this context if two constraints are set on the same device with
        the same target will overwrite the original one.
        At the end we ensure that there's only one constraint per device and
        target

        Args:
            constraints: Iterable of HTBConstraints
        """
        for constraint in constraints:
            matched = [sc for sc in self.constraints if self.equal(constraint, sc)]
            for c in matched:
                self.constraints.discard(c)
            self.constraints.add(constraint)
        return self

    @staticmethod
    def equal(c1: HTBConstraint, c2: HTBConstraint):
        """Encode the equality of two constraints in this context."""
        return (
            c1.__class__ == c2.__class__
            and c1.device == c2.device
            and c1.target == c2.target
        )

    def add_commands(self) -> List[str]:
        cmds: Set[str] = set()
        for constraint in self.constraints:
            cmds = cmds.union(set(constraint.add_commands()))
        return list(cmds)

    def remove_commands(self) -> List[str]:
        cmds: Set[str] = set()
        for constraint in self.constraints:
            cmds = cmds.union(set(constraint.remove_commands()))
        return list(cmds)

    def commands(self) -> List[str]:
        htb_cmds: List[str] = []
        for idx, tc in enumerate(self.constraints):
            # rate limit
            htb_cmds.extend(tc.commands(idx))
        return htb_cmds

    def all_commands(self) -> Tuple[List[str], List[str], List[str]]:
        return self.remove_commands(), self.add_commands(), self.commands()


def netem_htb(htb_hosts: List[HTBSource], chunk_size: int = 100, **kwargs):
    """Helper function to enforce heterogeneous limitations on hosts.

    This function do the heavy lifting of building the qdisc tree for each
    node and add filters based on the ip destination of the packet.
    Ref: https://tldp.org/HOWTO/Traffic-Control-HOWTO/classful-qdiscs.html

    This function is used internally by the
    :py:class:`enoslib.service.netem.netem.Netem` service. Here, you must
    ensure that the various :py:class:`enoslib.service.netem.netem.HTBSource`
    are consistent (e.g device names.) with the host.
    Symetric limitations can be achieved by adding both end of the
    communication to the list.
    The same host can appear multiple times in the list, all the constraints
    will be merged according to
    :py:meth:`enoslib.service.emul.htb.HTBSource.add_constraints`

    This method is optimized toward execution time: enforcing thousands of
    atomic constraints (= tc commands) shouldn't be a problem. Commands are
    sent by batch and ``chunk_size`` controls the size of the batch.

    Idempotency note: the existing qdiscs are removed before applying new
    ones. This must be safe in most of the cases to consider that this is a
    form of idempotency.

    Args:
        htb_hosts : list of constraints to apply.
        chunk_size: size of the chunk to use
        kwargs: keyword arguments passed to :py:fun:`enoslib.api.run_ansible`

    Examples:

        .. literalinclude:: ../tutorials/network_emulation/tuto_netem_htb.py
            :language: python
            :linenos:


    """
    # tc_commands are indexed by host alias == inventory_hostname
    tc_commands = _combine(*_build_commands(htb_hosts), chunk_size=chunk_size)
    extra_vars = kwargs.pop("extra_vars", {})
    options = _build_options(extra_vars, {"tc_commands": tc_commands})

    # Run the commands on the remote hosts (only those involved)
    roles = Roles(all=[htb_host.host for htb_host in htb_hosts])
    with play_on(roles=roles, extra_vars=options, **kwargs) as p:
        p.raw(
            "{{ item }}",
            when="tc_commands[inventory_hostname] is defined",
            loop="{{ tc_commands[inventory_hostname] }}",
            task_name="Applying the network constraints",
        )


class NetemHTB(Service):
    def __init__(
        self,
    ):
        """Set heterogeneous constraints on each host.

        It allows to setup complex network topology. For a much simpler way of
        applying constraints see
        :py:class:`~enoslib.service.emul.netem.Netem`

        The topology can be built by add constraints iteratively with
        :py:meth:`~enoslib.service.emul.htb.NetemHTB.add_constraints` or by
        passing a description as a dictionnary using the
        :py:meth:`~enoslib.service.emul.htb.NetemHTB.from_dict` class method.

        Args:
            roles: the enoslib roles to consider
            kwargs: keyword arguments passed to :py:func:`enoslib.api.run_ansible`
        """
        # populated later
        self.sources: Dict[Host, HTBSource] = dict()

    def add_constraints(
        self,
        src: List[Host],
        dest: List[Host],
        delay: str,
        rate: str,
        loss: Optional[float] = None,
        networks: Optional[List[Network]] = None,
        symetric: bool = False,
    ):
        """Add some constraints.

        Args:
            src: list of hosts on which the constraint will be applied
            dest: list of hosts to which traffic will be limited
            delay: the delay to apply as a string (e.g 10ms)
            rate: the rate to apply as a string (e.g 1gbit)
            loss: the percentage of loss (between 0 and 1)
            networks: only consider these networks when applying the
                resources (default to all networks)
            symetric: True iff the symetric rules should be also added.

        Examples:

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_build.py
                    :language: python
                    :linenos:

            - Using a secondary network from a list of constraints

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_b_second.py
                :language: python
                :linenos:

        Returns:
            The current service with updated constraints.
            (This allow to chain the addition of constraints)
        """
        for src_host in src:
            self.sources.setdefault(src_host, HTBSource(src_host))
            source = self.sources[src_host]
            local_devices = src_host.filter_interfaces(networks, include_unknown=False)
            for sdevice in local_devices:
                # one possible device
                for dest_host in dest:
                    # one possible destination
                    dall_addrs = dest_host.filter_addresses(
                        networks, include_unknown=False
                    )
                    for daddr in dall_addrs:
                        assert daddr.ip is not None
                        kwargs = dict(
                            device=str(sdevice),
                            target=str(daddr.ip.ip),
                            delay=delay,
                            rate=rate,
                            loss=loss,
                        )
                        source.add_constraint(**kwargs)
        if symetric:
            self.add_constraints(
                dest, src, delay, rate, loss=loss, networks=networks, symetric=False
            )
        return self

    @classmethod
    def from_dict(cls, network_constraints: Dict, roles: Roles, networks: Networks):
        """Build the service from a dictionnary describing the network topology.

        Args:
            network_constraints: Dictionnay of constraints. This must conform with
                :py:const:`~enoslib.service.emul.schema.SCHEMA`.


        Examples:

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb.py
                :language: python
                :linenos:

            Using a secondary network:

            .. literalinclude:: ../tutorials/network_emulation/tuto_svc_htb_secondary.py
                :language: python
                :linenos:


        """
        HTBValidator.validate(network_constraints)
        # defaults
        self = cls()
        groups = network_constraints.get("groups", list(roles.keys()))
        except_roles = network_constraints.get("except", [])
        selected = [roles[role] for role in groups if role not in except_roles]
        default_delay = network_constraints["default_delay"]
        default_rate = network_constraints["default_rate"]
        default_loss = network_constraints.get("default_loss")
        default_network_name = network_constraints.get("default_network")
        if default_network_name is not None:
            networks_list = networks[default_network_name]
        else:
            networks_list = []
        for src, dest in product(selected, selected):
            self.add_constraints(
                src,
                dest,
                default_delay,
                default_rate,
                default_loss,
                networks=networks_list,
            )
        # specific
        for constraint in network_constraints.get("constraints", []):
            src_role = constraint["src"]
            dest_role = constraint["dst"]
            delay = constraint.get("delay", default_delay)
            rate = constraint.get("rate", default_rate)
            loss = constraint.get("loss", default_loss)
            network_name = constraint.get("network", default_network_name)
            symetric = constraint.get("symetric", False)
            if network_name is not None:
                networks_list = networks[network_name]
            else:
                networks_list = []
            self.add_constraints(
                roles[src_role],
                roles[dest_role],
                delay,
                rate,
                loss,
                symetric=symetric,
                networks=networks_list,
            )
        return self

    def deploy(self, chunk_size: int = 100, **kwargs):
        sources = list(self.sources.values())
        netem_htb(sources, chunk_size=chunk_size, **kwargs)
        return sources

    def backup(self):
        """(Not Implemented) Backup.

        Feel free to share your ideas.
        """
        pass

    def destroy(self, **kwargs):
        """Reset the network constraints(latency, bandwidth ...)

        Remove any filter that have been applied to shape the traffic ever.

        Careful: This remove every rules, including those not managed by this service.
        """
        _destroy(list(self.sources.keys()), **kwargs)

    def validate(
        self, *, networks: Optional[List[Network]] = None, output_dir=None, **kwargs
    ):
        """Validate the network parameters(latency, bandwidth ...)

        Performs ping tests to validate the constraints set by
        :py:meth:`~enoslib.service.emul.htb.NetemHTB.deploy`.
        Reports are available in the putput directory.
        used by enos.

        Args:
            roles(dict): role -> hosts mapping as returned by
                : py: meth: `enoslib.infra.provider.Provider.init`
            inventory_path(str): path to an inventory
            output_dir(str): directory where validation files will be stored.
                Default to: py: const: `enoslib.constants.TMP_DIRNAME`.
        """
        _validate(
            list(self.sources.keys()),
            networks=networks,
            output_dir=output_dir,
            **kwargs,
        )
