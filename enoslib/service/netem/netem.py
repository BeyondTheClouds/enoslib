import copy
import logging
import re
import os
from typing import Dict, List, Generator
import yaml

from jsonschema import validate

from enoslib.api import run_ansible
from enoslib.constants import TMP_DIRNAME
from enoslib.utils import _check_tmpdir
from ..service import Service


SERVICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


logger = logging.getLogger(__name__)


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
    """Generate default symetric grp constraints.
    """
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
    """Generate the user specified constraints
    """
    if "constraints" not in network_constraints:
        return []

    constraints = network_constraints["constraints"]
    actual = []
    for desc in constraints:
        descs = _expand_description(desc)
        for desc in descs:
            actual.append(desc)
            if "symetric" in desc:
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


def _gen_devices(
    all_devices: List[Dict], enos_devices: List[str]
) -> Generator[Dict, None, None]:
    """Get the name of the physical device attached to this device.

    Args:
        devices: list of the devices to extract the names from

    If the device is a physical one return it
    If the device is a "virtual" one (e.g bridge) returns the
    corresponding physical ones.
    """
    for device in enos_devices:
        # get the device caracteristic
        _device = [d for d in all_devices if d["device"] == device][0]
        if _device["type"] == "bridge":
            for interface in _device["interfaces"]:
                _d = [d for d in all_devices if d["device"] == interface]
                yield _d[0]
        else:
            yield _device


def _build_ip_constraints(roles, ips, constraints):
    """Generate the constraints at the ip/device level.
    Those constraints are those used by ansible to enforce tc/netem rules.
    """
    local_ips = copy.deepcopy(ips)
    ip_constraints = {}
    for constraint in constraints:
        gsrc = constraint["src"]
        gdst = constraint["dst"]
        gdelay = constraint["delay"]
        grate = constraint["rate"]
        gloss = constraint["loss"]
        for s in roles[gsrc]:
            # one possible source
            local_devices = []
            if "network" in constraint:
                # Get only the devices specified in the network constraint
                local_devices = filter(
                    lambda x: x["device"] == s.extra[constraint["network"]],
                    local_ips[s.alias]["devices"],
                )
            else:
                # Get all the active devices for this source
                local_devices = _gen_devices(
                    local_ips[s.alias]["devices"], local_ips[s.alias]["enos_devices"]
                )

            for sdevice in local_devices:
                ip_constraints.setdefault(s.alias, {})
                ip_constraints[s.alias].setdefault("devices", [])
                # don't add a new device if it still there for the corresponding node
                check = [
                    d
                    for d in ip_constraints[s.alias]["devices"]
                    if d["device"] == sdevice["device"]
                ]
                if not check:
                    ip_constraints[s.alias]["devices"].append(sdevice)
                # one possible device
                for d in roles[gdst]:
                    # one possible destination
                    dallips = local_ips[d.alias]["all_ipv4_addresses"]
                    # Let's keep docker bridge out of this
                    dallips = filter(lambda x: x != "172.17.0.1", dallips)
                    for dip in dallips:
                        ip_constraints[s.alias].setdefault("tc", []).append(
                            {
                                # source identifies the inventory hostname
                                # used by ansible
                                "source": s.alias,
                                # Below is used for setting the right tc rules
                                "target": dip,
                                "device": sdevice["device"],
                                "delay": gdelay,
                                "rate": grate,
                                "loss": gloss,
                            }
                        )
    return ip_constraints


class Netem(Service):
    SCHEMA = {
        "type": "object",
        "properties": {
            "enable": {"type": "boolean"},
            "default_delay": {"type": "string"},
            "default_rate": {"type": "string"},
            "default_loss": {"type": "number"},
            "except": {"type": "array", "items": {"type": "string"}},
            "groups": {"type": "array", "items": {"type": "string"}},
            "constraints": {"type": "array", "items": {"$ref": "#/constraint"}},
        },
        "additionnalProperties": False,
        "required": ["default_delay", "default_rate"],
        "constraint": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
                "delay": {"type": "string"},
                "rate": {"type": "string"},
                "loss": {"type": "number"},
            },
            "additionnalProperties": False,
            "required": ["src", "dst"],
        },
    }

    def __init__(self, network_constraints, *, roles=None, extra_vars=None):

        validate(instance=network_constraints, schema=self.SCHEMA)
        self.network_constraints = network_constraints
        self.roles = roles if roles is not None else []
        self.extra_vars = extra_vars if extra_vars is not None else {}

    def deploy(self):
        """Emulate network links.

        Read ``network_constraints`` and apply ``tc`` rules on all the nodes.
        Constraints are applied between groups of machines. Theses groups are
        described in the ``network_constraints`` variable and must be found in
        the inventory file. The newtwork constraints support ``delay``,
        ``rate`` and ``loss``.

        Args:
            network_constraints (dict): network constraints to apply
            roles (dict): role->hosts mapping as returned by
                :py:meth:`enoslib.infra.provider.Provider.init`
            inventory_path(string): path to an inventory
            extra_vars (dict): extra_vars to pass to ansible

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
                    "enable": True,
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            If you want to control more precisely which groups need to be taken
            into account, you can use ``except`` or ``groups`` key

            .. code-block:: python

                tc = {
                    "enable": True,
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "except": "grp3"
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            If you want to control more precisely which groups need to be taken
            into account:

            .. code-block:: python

                tc = {
                    "enable": True,
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
                    "groups": ["grp1", "grp2"]
                }
                netem = Netem(tc, roles=roles)
                netem.deploy()

            * Using ``src`` and ``dst``

            The following will enforce a symetric constraint between ``grp1``
            and ``grp2``.

            .. code-block:: python

                tc = {
                    "enable": True,
                    "default_delay": "20ms",
                    "default_rate": "1gbit",
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
        # 1) Retrieve the list of ips for all nodes (Ansible)
        # 2) Build all the constraints (Python)
        #    {source:src, target: ip_dest, device: if, rate:x,  delay:y}
        # 3) Enforce those constraints (Ansible)

        # 1. getting  ips/devices information
        logger.debug("Getting the ips of all nodes")
        tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)
        _check_tmpdir(tmpdir)
        _playbook = os.path.join(SERVICE_PATH, "netem.yml")
        ips_file = os.path.join(tmpdir, "ips.txt")
        options = self._build_options({"enos_action": "tc_ips", "ips_file": ips_file})
        run_ansible([_playbook], roles=self.roles, extra_vars=options)

        # 2.a building the group constraints
        logger.debug("Building all the constraints")
        constraints = _build_grp_constraints(self.roles, self.network_constraints)
        # 2.b Building the ip/device level constaints
        with open(ips_file) as f:
            ips = yaml.safe_load(f)
            # will hold every single constraint
            ips_with_constraints = _build_ip_constraints(self.roles, ips, constraints)
            # dumping it for debugging purpose
            ips_with_constraints_file = os.path.join(tmpdir, "ips_with_constraints.yml")
            with open(ips_with_constraints_file, "w") as g:
                yaml.dump(ips_with_constraints, g)

        # 3. Enforcing those constraints
        logger.info("Enforcing the constraints")
        # enabling/disabling network constraints
        enable = self.network_constraints.setdefault("enable", True)
        options = self._build_options(
            {
                "enos_action": "tc_apply",
                "ips_with_constraints": ips_with_constraints,
                "tc_enable": enable,
            }
        )
        run_ansible([_playbook], roles=self.roles, extra_vars=options)

    def backup(self):
        """ What do you want to backup here?"""
        pass

    def destroy(self):
        """Reset the network constraints (latency, bandwidth ...)

        Remove any filter that have been applied to shape the traffic.
        """
        logger.debug("Reset the constraints")

        tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)
        _check_tmpdir(tmpdir)

        _playbook = os.path.join(SERVICE_PATH, "netem.yml")
        options = self._build_options(
            {"enos_action": "tc_reset", "tc_output_dir": tmpdir}
        )
        run_ansible([_playbook], roles=self.roles, extra_vars=options)

    def validate(self, *, output_dir=None):
        """Validate the network parameters (latency, bandwidth ...)

        Performs flent, ping tests to validate the constraints set by
        :py:meth:`enoslib.service.netem.Netem.deploy`.
        Reports are available in the tmp directory
        used by enos.

        Args:
            roles (dict): role->hosts mapping as returned by
                :py:meth:`enoslib.infra.provider.Provider.init`
            inventory_path (str): path to an inventory
            output_dir (str): directory where validation files will be stored.
                Default to :py:const:`enoslib.constants.TMP_DIRNAME`.
        """
        logger.debug("Checking the constraints")
        if not output_dir:
            output_dir = os.path.join(os.getcwd(), TMP_DIRNAME)

        output_dir = os.path.abspath(output_dir)
        _check_tmpdir(output_dir)
        _playbook = os.path.join(SERVICE_PATH, "netem.yml")
        options = self._build_options(
            {"enos_action": "tc_validate", "tc_output_dir": output_dir}
        )

        run_ansible([_playbook], roles=self.roles, extra_vars=options)

    def _build_options(self, options):
        _options = {}
        _options.update(self.extra_vars)
        _options.update(options)
        return _options
