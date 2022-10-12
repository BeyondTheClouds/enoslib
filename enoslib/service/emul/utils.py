import copy
from ipaddress import ip_interface
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple, Union
from enoslib.api import run_command
from enoslib.utils import _check_tmpdir
import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter

from enoslib.objects import Host, Network
from enoslib.api import actions, Results


FPING_FILE_SUFFIX = ".fpingout"

logger = logging.getLogger(__name__)


def _chunks(_list, size):
    """Chunk a list in smaller pieces."""
    for i in range(0, len(_list), size):
        yield _list[i : i + size]


def _combine(*args, separator=";", chunk_size=100):
    """Build the commands indexed by host."""
    c = defaultdict(list)
    _args = args
    for a in list(_args):
        for s, l in a.items():
            c[s] = c[s] + l
    commands = defaultdict(list)
    for alias in c.keys():
        for chunk in list(_chunks(c[alias], chunk_size)):
            commands[alias].append(f" {separator} ".join(chunk))
    return commands


def _build_options(extra_vars, options):
    """This only merges two dicts."""
    _options = {}
    _options.update(extra_vars)
    _options.update(options)
    return _options


def _build_commands(sources):
    """Source agnostic way of recombining the list of constraints."""
    _remove = defaultdict(list)
    _add = defaultdict(list)
    _htb = defaultdict(list)
    # intent make sure there's only one htbhost per host( = per alias)
    # so we merge all the constraints for a given host to a single one
    _sources = sorted(sources, key=attrgetter("host"))
    grouped = groupby(_sources, key=attrgetter("host"))

    new_sources = []
    for alias, group in grouped:
        first = copy.deepcopy(next(group))
        for _source in group:
            first.add_constraints(_source.constraints)
        new_sources.append(first)

    # assert: there's only one Source per host
    for source in new_sources:
        # generate devices based command (remove + add qdisc)
        alias = source.host.alias
        (
            _remove[alias],
            _add[alias],
            _htb[alias],
        ) = source.all_commands()
    return _remove, _add, _htb


def validate_delay(
    hosts: Iterable[Host],
    all_addresses: List[str],
    count: int = 10,
    **kwargs,
) -> Results:
    logger.debug("Checking the constraints")
    with actions(roles=hosts, extra_vars=kwargs.pop("extra_vars", {})) as a:
        # NOTE(msimonin): ideally we'll want this to work offline if the packet
        # is already there
        a.raw("which fping || apt install -y fping", task="Check fping")
        a.raw(f"fping -C {count} -q -s -e {' '.join(all_addresses)}", task_name="fping")
        results = a.results
    return results.filter(task="fping")


def _validate(
    hosts: Iterable[Host],
    networks: Optional[Iterable[Network]] = None,
    output_dir: Optional[Union[Path, str]] = None,
    count: int = 10,
    **kwargs,
) -> Results:
    all_addresses: Set[str] = set()
    for host in hosts:
        addresses = host.filter_addresses(networks)
        all_addresses = all_addresses.union(
            {str(addr.ip.ip) for addr in addresses if addr.ip}
        )
    results = validate_delay(hosts, list(all_addresses), count=count, **kwargs)
    # save it if needed
    if output_dir is not None:
        _check_tmpdir(output_dir)
        output_dir = Path(output_dir)
        for result in results:
            # one per host
            (output_dir / result.host).with_suffix(FPING_FILE_SUFFIX).write_text(
                result.stdout
            )
    return results


def _destroy(hosts: Iterable[Host], **kwargs):
    logger.debug("Reset the constraints")

    extra_vars = kwargs.pop("extra_vars", {})
    run_command(
        "tc qdisc del dev {{ item }} root || true",
        loop="{{ansible_interfaces}}",
        roles=hosts,
        extra_vars=extra_vars,
        gather_facts=True,
    )


def _fping_stats(lines: List[str]) -> List[Tuple[str, List[float]]]:
    results: List[Tuple[str, List[float]]] = []
    for line in lines:
        try:
            # may fail if this isn't the head of the file
            # beware that ipv6 may contain : too!
            dst, values = line.split(" : ")
            # may fail if addr isn't an address
            _ = ip_interface(dst.strip())
            pings = [float(v) for v in values.strip().split(" ")]
            results.append((dst.strip(), pings))
        except ValueError:
            continue
    return results
