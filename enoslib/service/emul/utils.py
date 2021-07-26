import copy
from typing import List, Optional, Set
from enoslib.api import run_ansible
from enoslib.utils import _check_tmpdir
from enoslib.constants import TMP_DIRNAME
import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
import os

from enoslib.objects import Host, Network

SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
PLAYBOOK = os.path.join(SERVICE_PATH, "netem.yml")
TMP_DIR = os.path.join(os.getcwd(), TMP_DIRNAME)

logger = logging.getLogger(__name__)


def _chunks(_list, size):
    """Chunk a list in smaller pieces."""
    for i in range(0, len(_list), size):
        yield _list[i: i + size]


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
    hosts: List[Host], output_dir: str, all_addresses: List[str], **kwargs
):
    logger.debug("Checking the constraints")
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), TMP_DIRNAME)

    extra_vars = kwargs.pop("extra_vars", {})
    output_dir = os.path.abspath(output_dir)
    _check_tmpdir(output_dir)
    _playbook = os.path.join(SERVICE_PATH, "netem.yml")
    options = _build_options(
        extra_vars,
        dict(
            enos_action="tc_validate",
            tc_output_dir=output_dir,
            all_addresses=all_addresses,
        ),
    )
    run_ansible([_playbook], roles=hosts, extra_vars=options, **kwargs)


def _validate(
    hosts: List[Host],
    networks: Optional[List[Network]] = None,
    output_dir=None,
    **kwargs,
):
    all_addresses: Set[str] = set()
    for host in hosts:
        addresses = host.filter_addresses(networks)
        all_addresses = all_addresses.union(
            set([str(addr.ip.ip) for addr in addresses if addr.ip])
        )
    validate_delay(hosts, output_dir, list(all_addresses), **kwargs)


def _destroy(hosts: List[Host], **kwargs):
    logger.debug("Reset the constraints")

    _check_tmpdir(TMP_DIR)

    _playbook = os.path.join(SERVICE_PATH, "netem.yml")
    extra_vars = kwargs.pop("extra_vars", {})
    options = _build_options(
        extra_vars, {"enos_action": "tc_reset", "tc_output_dir": TMP_DIR}
    )
    run_ansible([_playbook], roles=hosts, extra_vars=options)
