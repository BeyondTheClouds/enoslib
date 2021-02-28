"""HTB based emulation."""
from enoslib.utils import _check_tmpdir
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

from enoslib.api import play_on, run_ansible
from enoslib.constants import TMP_DIRNAME
from enoslib.objects import Host, Networks, Roles
from jsonschema import validate

from ..service import Service
from .schema import SCHEMA
from .utils import (
    _build_commands,
    _build_grp_constraints,
    _build_options,
    _combine,
    _validate,
)

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
PLAYBOOK = os.path.join(SERVICE_PATH, "netem.yml")
TMP_DIR = os.path.join(os.getcwd(), TMP_DIRNAME)

DEFAULT_RATE = "10gbit"

DEFAULT_LOSS = "0"


logger = logging.getLogger(__name__)


def _build_ip_constraints(
    roles: Roles, networks: Networks, constraints: Mapping
) -> List["HTBSource"]:
    """Generate the constraints at the ip/device level.

    Those constraints are those used by ansible to enforce tc/netem rules.
    """
    host_htbs = []
    for constraint in constraints:
        gsrc = constraint["src"]
        gdst = constraint["dst"]
        gdelay = constraint["delay"]
        grate = constraint["rate"]
        gloss = constraint["loss"]
        for source_host in roles[gsrc]:
            # one possible source

            # 1) we get all the devices for the wanted networks
            nets = None
            if "networks" in constraints and networks is not None:
                _netss = [
                    networks
                    for role, networks in networks.items()
                    if {role}.issubset(set(constraints["networks"]))
                ]
                nets = []
                for _nets in _netss:
                    nets.extend(_nets)
            local_devices = source_host.filter_interfaces(nets, include_unknown=False)

            host_htb = HTBSource(host=source_host)
            for sdevice in local_devices:
                # one possible device
                for d in roles[gdst]:
                    # one possible destination
                    dall_addrs = d.filter_addresses(nets, include_unknown=False)
                    # Let's keep docker bridge out of this
                    for daddr in dall_addrs:
                        assert daddr.ip is not None
                        host_htb.add_constraint(
                            target=str(daddr.ip.ip),
                            device=str(sdevice),
                            delay=gdelay,
                            rate=grate,
                            loss=gloss,
                        )
            host_htbs.append(host_htb)
    return host_htbs


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
    loss: str = DEFAULT_LOSS

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

        if self.loss == 0:
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
        self.constraints.add(HTBConstraint(*args, **kwargs))

    def add_constraints(self, constraints: Iterable[HTBConstraint]):
        self.constraints = self.constraints.union(set(constraints))

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
    will be concatenated.

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
    roles = dict(all=[htb_host.host for htb_host in htb_hosts])
    with play_on(roles=roles, extra_vars=options, **kwargs) as p:
        p.raw(
            "{{ item }}",
            when="tc_commands[inventory_hostname] is defined",
            loop="{{ tc_commands[inventory_hostname] }}",
            display_name="Applying the network constraints",
        )


class NetemHTB(Service):
    def __init__(
        self,
        network_constraints: Dict[Any, Any],
        *,
        roles: Roles = None,
        networks: Networks = None,
        chunk_size: int = 100,
        **kwargs,
    ):
        """Set heterogeneous constraints between your hosts.

        It allows to setup complex network topology. For a much simpler way of
        applying constraints see
        :py:class:`enoslib.service.netem.SimpleNetem`

        Args:
            network_constraints: the decription of the wanted constraints
                (see the schema below)
            roles: the enoslib roles to consider
            chunk_size: For large deployments, the commands to apply can become too
                long. It can be split in chunks of size chunk_size.
            kwargs: keyword arguments passed to :py:fun:`enoslib.api.run_ansible`

        *Network constraint schema:*

            .. literalinclude:: ../../enoslib/service/netem/schema.py
                :language: python
                :linenos:

        Examples:

            * Using defaults

            The following will apply the network constraints between every
            groups. For instance the constraints will be applied for the
            communication between "n1" and "n3" but not between "n1" and "n2".
            Note that using default leads to symetric constraints.

            .. code-block:: python

                roles = {
                    "grp1": ["n1", "n2"],
                    "grp2": ["n3", "n4"],
                    "grp3": ["n3", "n4"],
                }

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "groups": ["grp1", "grp2", "grp3"]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            Symetricaly, you can use ``except`` to exclude some groups.

            .. code-block:: python

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "except": ["grp3"]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            ``except: []`` is a way to apply the constraints between all groups.

            * Using ``src`` and ``dst``

            The following will enforce a symetric constraint between ``grp1``
            and ``grp2``.

            .. code-block:: python

                tc = {
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "groups": ["grp1", "grp2"]
                    "constraints": [{
                        "src": "grp1"
                        "dst": "grp2"
                        "delay": "10ms"
                        "symetric": True
                    }]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

        Examples:

            .. literalinclude:: examples/netem.py
              :language: python
              :linenos:

        """
        NetemHTB.is_valid(network_constraints)
        self.network_constraints = network_constraints
        self.roles = roles if roles is not None else []
        self.networks = networks
        self.kwargs = kwargs
        self.chunk_size = chunk_size

    @classmethod
    def is_valid(cls, network_constraints):
        """Validate the network_constraints (syntax only)."""
        return validate(instance=network_constraints, schema=SCHEMA)

    def deploy(self):
        """Enforce network links emulation."""
        # 1. Build all the constraints (Python)
        #    {source:src, target: ip_dest, device: if, rate:x,  delay:y}
        # 2. Generate the sequence of tc commands to run on the hosts (Python)
        # 3. Run those commands (Ansible)

        # 2.a building the group constraints
        logger.debug("Building all the constraints")
        constraints = _build_grp_constraints(self.roles, self.network_constraints)
        # 2.b Building the ip/device level constaints

        # will hold every single constraint
        host_htbs = _build_ip_constraints(self.roles, self.networks, constraints)

        # 3. Building the sequence of tc commands
        logger.info("Enforcing the constraints")

        netem_htb(host_htbs, chunk_size=self.chunk_size, **self.kwargs)

    def backup(self):
        """(Not Implemented) Backup.

        Feel free to share your ideas.
        """
        pass

    def destroy(self):
        """Reset the network constraints(latency, bandwidth ...)

        Remove any filter that have been applied to shape the traffic.
        """
        logger.debug("Reset the constraints")

        _check_tmpdir(TMP_DIR)

        _playbook = os.path.join(SERVICE_PATH, "netem.yml")
        extra_vars = self.kwargs.pop("extra_vars", {})
        options = _build_options(
            extra_vars, {"enos_action": "tc_reset", "tc_output_dir": TMP_DIR}
        )
        run_ansible([_playbook], roles=self.roles, extra_vars=options)

    def validate(self, *, output_dir=None):
        """Validate the network parameters(latency, bandwidth ...)

        Performs ping tests to validate the constraints set by
        :py:meth:`enoslib.service.netem.Netem.deploy`.
        Reports are available in the tmp directory
        used by enos.

        Args:
            roles(dict): role -> hosts mapping as returned by
                : py: meth: `enoslib.infra.provider.Provider.init`
            inventory_path(str): path to an inventory
            output_dir(str): directory where validation files will be stored.
                Default to: py: const: `enoslib.constants.TMP_DIRNAME`.
        """
        all_addresses = set()
        for hosts in self.roles.values():
            for host in hosts:
                addresses = host.filter_addresses(self.networks)
                all_addresses = all_addresses.union(
                    set([str(addr.ip.ip) for addr in addresses])
                )
        _validate(self.roles, output_dir, list(all_addresses))
