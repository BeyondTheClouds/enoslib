# -*- coding: utf-8 -*-
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from collections import namedtuple
from enoslib.constants import ANSIBLE_DIR, TMP_DIRNAME
from enoslib.utils import _expand_groups, _check_tmpdir
from errors import (EnosFailedHostsError,
                    EnosUnreachableHostsError,
                    EnosSSHNotReady)
from netaddr import IPAddress, IPSet

import copy
import logging
import os
import time
import yaml


def run_ansible(playbooks, inventory_path, extra_vars=None,
        tags=None, on_error_continue=False):
    """Run Ansible.

    Args:
        playbooks (list): list of paths to the playbooks to run
        inventory_path (str): path to the hosts file (inventory)
        extra_var (dict): extra vars to pass
        tags (list): list of tags to run
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``
    """
    extra_vars = extra_vars or {}
    variable_manager = VariableManager()
    loader = DataLoader()

    inventory = Inventory(loader=loader,
        variable_manager=variable_manager,
        host_list=inventory_path)

    variable_manager.set_inventory(inventory)

    if extra_vars:
        variable_manager.extra_vars = extra_vars

    if tags is None:
        tags = []

    passwords = {}
    # NOTE(msimonin): The ansible api is "low level" in the
    # sense that we are redefining here all the default values
    # that are usually enforce by ansible called from the cli
    Options = namedtuple("Options", ["listtags", "listtasks",
                                     "listhosts", "syntax",
                                     "connection", "module_path",
                                     "forks", "private_key_file",
                                     "ssh_common_args",
                                     "ssh_extra_args",
                                     "sftp_extra_args",
                                     "scp_extra_args", "become",
                                     "become_method", "become_user",
                                     "remote_user", "verbosity",
                                     "check", "tags", "pipelining"])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection="ssh",
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=None,
                      become_method="sudo", become_user="root",
                      remote_user=None, verbosity=2, check=False,
                      tags=tags, pipelining=True)

    for path in playbooks:
        logging.info("Running playbook %s with vars:\n%s" % (path, extra_vars))

        pbex = PlaybookExecutor(
            playbooks=[path],
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=options,
            passwords=passwords
        )

        code = pbex.run()
        stats = pbex._tqm._stats
        hosts = stats.processed.keys()
        result = [{h: stats.summarize(h)} for h in hosts]
        results = {"code": code, "result": result, "playbook": path}
        print(results)

        failed_hosts = []
        unreachable_hosts = []

        for h in hosts:
            t = stats.summarize(h)
            if t["failures"] > 0:
                failed_hosts.append(h)

            if t["unreachable"] > 0:
                unreachable_hosts.append(h)

        if len(failed_hosts) > 0:
            logging.error("Failed hosts: %s" % failed_hosts)
            if not on_error_continue:
                raise EnosFailedHostsError(failed_hosts)
        if len(unreachable_hosts) > 0:
            logging.error("Unreachable hosts: %s" % unreachable_hosts)
            if not on_error_continue:
                raise EnosUnreachableHostsError(unreachable_hosts)


def generate_inventory(roles, networks, inventory_path, check_networks=False,
        fake_interfaces=None):
    """Generate an inventory file in the ini format.

    The inventory is generated using the ``roles`` in the ``ini`` format.  If
    ``check_network == True``, the function will try to discover which networks
    interfaces are available and map them to one network of the ``networks``
    parameters.  Note that this auto-discovery feature requires the servers to
    have their IP set.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        networks (list): network list as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory_path (str): path to the inventory to generate
        check_networks (bool): True to enable the auto-discovery of the mapping
            interface name <-> network role
        fake_interfaces (list): names of optionnal dummy interfaces to create
            on the nodes
    """

    with open(inventory_path, "w") as f:
            f.write(_generate_inventory(roles))
    if check_networks:
        _check_networks(
            roles,
            networks,
            inventory_path,
            fake_interfaces=fake_interfaces)
        with open(inventory_path, "w") as f:
            f.write(_generate_inventory(roles))


def emulate_network(roles, inventory, network_constraints):
    """Emulate network links.

    Read ``network_constraints`` and apply ``tc`` rules on all the nodes.
    Constraints are applied between groups of machines. Theses groups are
    described in the ``network_constraints`` variable and must be found in the
    inventory file. The newtwork constraints support ``delay``, ``rate`` and
    ``loss``.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory (str): path to the inventory
        network_constraints (dict): network constraints to apply

    Examples:

        * Using defaults

        The following will apply the network constraints between every groups.
        For instance the constraints will be applied for the communication
        between "n1" and "n3" but not between "n1" and "n2". Note that using
        default leads to symetric constraints.

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
            emulate_network(roles, inventory, tc)

        If you want to control more precisely which groups need to be taken
        into account, you can use ``except`` or ``groups`` key

        .. code-block:: python

            tc = {
                "enable": True,
                "default_delay": "20ms",
                "default_rate": "1gbit",
                "except": "grp3"
            }
            emulate_network(roles, inventory, tc)

        is equivalent to

        .. code-block:: python

            tc = {
                "enable": True,
                "default_delay": "20ms",
                "default_rate": "1gbit",
                "groups": ["grp1", "grp2"]
            }
            emulate_network(roles, inventory, tc)

        * Using ``src`` and ``dst``

        The following will enforce a symetric constraint between ``grp1`` and
        ``grp2``.

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
            emulate_network(roles, inventory, tc)

    """
    # 1) Retrieve the list of ips for all nodes (Ansible)
    # 2) Build all the constraints (Python)
    #    {source:src, target: ip_dest, device: if, rate:x,  delay:y}
    # 3) Enforce those constraints (Ansible)

    # TODO(msimonin)
    #    - allow finer grained filtering based on network roles and/or nic name

    # 1. getting  ips/devices information
    logging.debug('Getting the ips of all nodes')
    tmpdir = os.path.join(os.path.dirname(inventory), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
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
    :py:func:`emulate_network`. Reports are available in the tmp directory used
    by enos.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory (str): path to the inventory
    """
    logging.debug('Checking the constraints')
    tmpdir = os.path.join(os.path.dirname(inventory), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'enos_action': 'tc_validate',
               'tc_output_dir': tmpdir}
    run_ansible([utils_playbook], inventory, extra_vars=options)


def wait_ssh(inventory, retries=100, interval=30):
    """Wait for all the machines to be ssh-reachable

    Let ansible initiates a communication and retries if needed.

    Args:
        inventory (string): path to the inventoy file to test
        retries (int): Number of time we'll be retrying an SSH connection
        interval (int): Interval to wait in seconds between two retries
    """
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'enos_action': 'ping'}

    for i in range(0, retries):
        try:
            run_ansible([utils_playbook],
                        inventory,
                        extra_vars=options,
                        on_error_continue=False)
            break
        except EnosUnreachableHostsError as e:
            logging.info("Hosts unreachable: %s " % e.hosts)
            logging.info("Retrying... %s/%s" % (i + 1, retries))
            time.sleep(interval)
    else:
        raise EnosSSHNotReady('Maximum retries reached')


def _generate_inventory(roles):
    """Generates an inventory files from roles

    :param roles: dict of roles (roles -> list of Host)
    """
    inventory = []
    for role, desc in roles.items():
        inventory.append("[%s]" % role)
        inventory.extend([_generate_inventory_string(d) for d in desc])
    return "\n".join(inventory)


def _generate_inventory_string(host):
    def to_inventory_string(v):
        """Handle the cas of List[String]."""
        if isinstance(v, list):
            # [a, b, c] -> "['a','b','c']"
            s = map(lambda x: "'%s'" % x, v)
            s = "\"[%s]\"" % ','.join(s)
            return s
        return v

    i = [host.alias, "ansible_host=%s" % host.address]
    if host.user is not None:
        i.append("ansible_ssh_user=%s" % host.user)
    if host.port is not None:
        i.append("ansible_port=%s" % host.port)
    if host.keyfile is not None:
        i.append("ansible_ssh_private_key_file=%s" % host.keyfile)
    # Disabling hostkey ckecking
    common_args = []
    common_args.append("-o StrictHostKeyChecking=no")
    common_args.append("-o UserKnownHostsFile=/dev/null")
    forward_agent = host.extra.get('forward_agent', False)
    if forward_agent:
        common_args.append("-o ForwardAgent=yes")

    gateway = host.extra.get('gateway', None)
    if gateway is not None:
        proxy_cmd = ["ssh -W %h:%p"]
        # Disabling also hostkey checking for the gateway
        proxy_cmd.append("-o StrictHostKeyChecking=no")
        proxy_cmd.append("-o UserKnownHostsFile=/dev/null")
        gateway_user = host.extra.get('gateway_user', host.user)
        if gateway_user is not None:
            proxy_cmd.append("-l %s" % gateway_user)

        proxy_cmd.append(gateway)
        proxy_cmd = " ".join(proxy_cmd)
        common_args.append("-o ProxyCommand=\"%s\"" % proxy_cmd)

    common_args = " ".join(common_args)
    i.append("ansible_ssh_common_args='%s'" % common_args)

    # Add custom variables
    for k, v in host.extra.items():
        if k not in ["gateway", "gateway_user", "forward_agent"]:
            i.append("%s=%s" % (k, to_inventory_string(v)))
    return " ".join(i)


def _update_hosts(roles, facts, extra_mapping=None):
    # Update every hosts in roles
    # NOTE(msimonin): due to the deserialization
    # between phases, hosts in rsc are unique instance so we need to update
    # every single host in every single role
    extra_mapping = extra_mapping or {}
    for hosts in roles.values():
        for host in hosts:
            networks = facts[host.alias]['networks']
            enos_devices = []
            for network in networks:
                device = network["device"]
                if device:
                    for role in network["roles"]:
                        host.extra.update({role: device})
                    enos_devices.append(device)

            # Add the list of devices in used by Enos
            host.extra.update({'enos_devices': enos_devices})


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
    grps = network_constraints.get('groups', roles.keys())
    # expand each groups
    grps = [_expand_groups(g) for g in grps]
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


def _check_networks(roles, networks, inventory, fake_interfaces=None):
    """Checks the network interfaces on the nodes

    Beware, this has a side effect on each Host in env['rsc'].
    """
    def get_devices(facts):
        """Extract the network devices information from the facts."""
        devices = []
        for interface in facts['ansible_interfaces']:
            ansible_interface = 'ansible_' + interface
            # filter here (active/ name...)
            if 'ansible_' + interface in facts:
                interface = facts[ansible_interface]
                devices.append(interface)
        return devices
    tmpdir = os.path.join(os.path.dirname(inventory), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
    fake_interfaces = fake_interfaces or []
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    facts_file = os.path.join(tmpdir, 'facts.yml')
    options = {
        'enos_action': 'check_network',
        'facts_file': facts_file,
        'fake_interfaces': fake_interfaces
    }
    run_ansible([utils_playbook], inventory,
        extra_vars=options,
        on_error_continue=False)

    # Read the file
    # Match provider networks to interface names for each host
    with open(facts_file) as f:
        facts = yaml.load(f)
        for _, host_facts in facts.items():
            host_nets = _map_device_on_host_networks(networks,
                                                    get_devices(host_facts))
            # Add the mapping : networks <-> nic name
            host_facts['networks'] = host_nets

    # Finally update the env with this information
    _update_hosts(roles, facts)


def _map_device_on_host_networks(provider_nets, devices):
    """Decorate each networks with the corresponding nic name."""
    networks = copy.deepcopy(provider_nets)
    for network in networks:
        for device in devices:
            network.setdefault('device', None)
            ip_set = IPSet([network['cidr']])
            if 'ipv4' not in device:
                continue
            ips = device['ipv4']
            if not isinstance(ips, list):
                ips = [ips]
            if len(ips) < 1:
                continue
            ip = IPAddress(ips[0]['address'])
            if ip in ip_set:
                network['device'] = device['device']
                continue
    return networks
