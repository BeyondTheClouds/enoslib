from enoslib.ansible_utils import run_ansible
from enoslib.constants import ANSIBLE_DIR
from enoslib.utils import _expand_groups

import copy
import logging
import os
import yaml


def emulate_network(roles, inventory, network_constraints):
    """Emulate network links.

    Read ``network_constraints`` and apply ``tc`` rules on all the nodes.

    Args:
        roles (dict):
        inventory (str):
        network_constraints (dict):
    """
    # 1) Retrieve the list of ips for all nodes (Ansible)
    # 2) Build all the constraints (Python)
    #    {source:src, target: ip_dest, device: if, rate:x,  delay:y}
    # 3) Enforce those constraints (Ansible)

    # TODO(msimonin)
    #    - allow finer grained filtering based on network roles and/or nic name

    # 1. getting  ips/devices information
    logging.debug('Getting the ips of all nodes')
    tmpdir = os.path.dirname(inventory)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    ips_file = os.path.join(tmpdir, 'ips.txt')
    options = {'enos_action': 'tc_ips',
               'ips_file': ips_file}
    run_ansible([utils_playbook], inventory, extra_vars=options)

    # 2.a building the group constraints
    logging.debug('Building all the constraints')
    constraints = _build_grp_constraints(roles, network_constraints)
    # 2.b Building the ip/device level constaints
    with open(ips_file) as f:
        ips = yaml.load(f)
        # will hold every single constraint
        ips_with_constraints = _build_ip_constraints(roles,
                                                    ips,
                                                    constraints)
        # dumping it for debugging purpose
        ips_with_constraints_file = os.path.join(tmpdir,
                                                 'ips_with_constraints.yml')
        with open(ips_with_constraints_file, 'w') as g:
            yaml.dump(ips_with_constraints, g)

    # 3. Enforcing those constraints
    logging.info('Enforcing the constraints')
    # enabling/disabling network constraints
    enable = network_constraints.setdefault('enable', True)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {
        'enos_action': 'tc_apply',
        'ips_with_constraints': ips_with_constraints,
        'tc_enable': enable,
    }
    run_ansible([utils_playbook], inventory, extra_vars=options)


def validate_network(roles, inventory):
    """Validate the network parameters (latency, bandwidth ...)

    Performs flent, ping tests to validate the constraints set by
        :py:func:`emulate_network`

    Args:
        roles (dict):
        inventory (str)
    """
    logging.debug('Checking the constraints')
    tmpdir = os.path.dirname(inventory)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'enos_action': 'tc_validate',
               'tc_output_dir': tmpdir}
    run_ansible([utils_playbook], inventory, extra_vars=options)


def _expand_description(desc):
    """Expand the description given the group names/patterns
    e.g:
    {src: grp[1-3], dst: grp[4-6] ...} will generate 9 descriptions
    """
    srcs = _expand_groups(desc['src'])
    dsts = _expand_groups(desc['dst'])
    descs = []
    for src in srcs:
        for dst in dsts:
            local_desc = desc.copy()
            local_desc['src'] = src
            local_desc['dst'] = dst
            descs.append(local_desc)

    return descs


def _same(g1, g2):
    """Two network constraints are equals if they have the same
    sources and destinations
    """
    return g1['src'] == g2['src'] and g1['dst'] == g2['dst']


def _generate_default_grp_constraints(roles, network_constraints):
    """Generate default symetric grp constraints.
    """
    default_delay = network_constraints.get('default_delay')
    default_rate = network_constraints.get('default_rate')
    default_loss = network_constraints.get('default_loss', 0)
    except_groups = network_constraints.get('except', [])
    # expand each groups
    grps = map(lambda g: _expand_groups(g), roles.keys())
    # flatten
    grps = [x for expanded_group in grps for x in expanded_group]
    # building the default group constraints
    return [{
            'src': grp1,
            'dst': grp2,
            'delay': default_delay,
            'rate': default_rate,
            'loss': default_loss
        } for grp1 in grps for grp2 in grps
        if grp1 != grp2 and grp1 not in except_groups and
            grp2 not in except_groups]


def _generate_actual_grp_constraints(network_constraints):
    """Generate the user specified constraints
    """
    if 'constraints' not in network_constraints:
        return []

    constraints = network_constraints['constraints']
    actual = []
    for desc in constraints:
        descs = _expand_description(desc)
        for desc in descs:
            actual.append(desc)
            if 'symetric' in desc:
                sym = desc.copy()
                sym['src'] = desc['dst']
                sym['dst'] = desc['src']
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
    constraints = _generate_default_grp_constraints(roles,
                                                   network_constraints)
    # Updating the constraints if necessary
    if 'constraints' in network_constraints:
        actual = _generate_actual_grp_constraints(network_constraints)
        _merge_constraints(constraints, actual)

    return constraints


def _build_ip_constraints(roles, ips, constraints):
    """Generate the constraints at the ip/device level.
    Those constraints are those used by ansible to enforce tc/netem rules.
    """
    local_ips = copy.deepcopy(ips)
    for constraint in constraints:
        gsrc = constraint['src']
        gdst = constraint['dst']
        gdelay = constraint['delay']
        grate = constraint['rate']
        gloss = constraint['loss']
        for s in roles[gsrc]:
            # one possible source
            # Get all the active devices for this source
            active_devices = filter(lambda x: x["active"],
                                    local_ips[s.alias]['devices'])
            # Get only the name of the active devices
            sdevices = map(lambda x: x['device'], active_devices)
            for sdevice in sdevices:
                # one possible device
                for d in roles[gdst]:
                    # one possible destination
                    dallips = local_ips[d.alias]['all_ipv4_addresses']
                    # Let's keep docker bridge out of this
                    dallips = filter(lambda x: x != '172.17.0.1', dallips)
                    for dip in dallips:
                        local_ips[s.alias].setdefault('tc', []).append({
                            'source': s.alias,
                            'target': dip,
                            'device': sdevice,
                            'delay': gdelay,
                            'rate': grate,
                            'loss': gloss
                        })
    return local_ips
