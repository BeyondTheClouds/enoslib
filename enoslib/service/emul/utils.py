import copy
from typing import List
from enoslib.api import run_ansible
from enoslib.utils import _check_tmpdir
from enoslib.constants import TMP_DIRNAME
import logging
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
import os
import re

from enoslib.objects import Roles

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


def _validate(
    roles: Roles, output_dir: str, all_addresses: List[str], **kwargs
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
    run_ansible([_playbook], roles=roles, extra_vars=options, **kwargs)


def expand_groups(grp):
    """Expand group names.

    Args:
        grp (string): group names to expand

    Returns:
        list of groups

    Examples:

        * grp[1-3] will be expanded to [grp1, grp2, grp3]
        * grp1 will be expanded to [grp1]
    """
    p = re.compile(r"(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\]")
    m = p.match(grp)
    if m is not None:
        s = int(m.group("start"))
        e = int(m.group("end"))
        n = m.group("name")
        return list(map(lambda x: n + str(x), range(s, e + 1)))
    else:
        return [grp]


def _expand_description(desc):
    """Expand the description given the group names/patterns
    e.g:
    {src: grp[1-3], dst: grp[4-6] ...} will generate 9 descriptions
    """
    srcs = expand_groups(desc["src"])
    dsts = expand_groups(desc["dst"])
    descs = []
    for src in srcs:
        for dst in dsts:
            local_desc = desc.copy()
            local_desc["src"] = src
            local_desc["dst"] = dst
            descs.append(local_desc)

    return descs


def _src_equals_dst_in_constraints(network_constraints, grp1):
    if "constraints" in network_constraints:
        constraints = network_constraints["constraints"]
        for desc in constraints:
            descs = _expand_description(desc)
            for d in descs:
                if grp1 == d["src"] and d["src"] == d["dst"]:
                    return True
    return False


def _same(g1, g2):
    """Two network constraints are equals if they have the same
    sources and destinations
    """
    return g1["src"] == g2["src"] and g1["dst"] == g2["dst"]


def _generate_default_grp_constraints(roles, network_constraints):
    """Generate default symetric grp constraints."""
    default_delay = network_constraints.get("default_delay")
    default_rate = network_constraints.get("default_rate")
    default_loss = network_constraints.get("default_loss", 0)
    except_groups = network_constraints.get("except", [])
    grps = network_constraints.get("groups", roles.keys())
    # expand each groups
    grps = [expand_groups(g) for g in grps]
    # flatten
    grps = [x for expanded_group in grps for x in expanded_group]
    # building the default group constraints
    return [
        {
            "src": grp1,
            "dst": grp2,
            "delay": default_delay,
            "rate": default_rate,
            "loss": default_loss,
        }
        for grp1 in grps
        for grp2 in grps
        if (
            (grp1 != grp2 or _src_equals_dst_in_constraints(network_constraints, grp1))
            and grp1 not in except_groups
            and grp2 not in except_groups
        )
    ]


def _generate_actual_grp_constraints(network_constraints):
    """Generate the user specified constraints"""
    if "constraints" not in network_constraints:
        return []

    constraints = network_constraints["constraints"]
    actual = []
    for desc in constraints:
        descs = _expand_description(desc)
        for desc in descs:
            actual.append(desc)
            if "symetric" in desc and desc["symetric"]:
                sym = desc.copy()
                sym["src"] = desc["dst"]
                sym["dst"] = desc["src"]
                actual.append(sym)
    return actual


def _merge_constraints(constraints, overrides):
    """Merge the constraints avoiding duplicates
    Change constraints in place.
    """
    for o in overrides:
        i = 0
        while i < len(constraints):
            c = constraints[i]
            if _same(o, c):
                constraints[i].update(o)
                break
            i = i + 1


def _build_grp_constraints(roles, network_constraints):
    """Generate constraints at the group level,
    It expands the group names and deal with symetric constraints.
    """
    # generate defaults constraints
    constraints = _generate_default_grp_constraints(roles, network_constraints)
    # Updating the constraints if necessary
    if "constraints" in network_constraints:
        actual = _generate_actual_grp_constraints(network_constraints)
        _merge_constraints(constraints, actual)

    return constraints
