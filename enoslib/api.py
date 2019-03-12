# -*- coding: utf-8 -*-
from collections import namedtuple
import copy
import logging
import os
import re
import tempfile
import time
import json
import yaml


from ansible.executor import task_queue_manager
from ansible.executor.playbook_executor import PlaybookExecutor
# Note(msimonin): PRE 2.4 is
# from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.playbook import play
from ansible.plugins.callback.default import CallbackModule
# Note(msimonin): PRE 2.4 is
# from ansible.vars import VariableManager
from ansible.vars.manager import VariableManager
from netaddr import IPAddress, IPSet

from enoslib.constants import ANSIBLE_DIR, TMP_DIRNAME
from enoslib.enos_inventory import EnosInventory
from enoslib.utils import _check_tmpdir, get_roles_as_list
from enoslib.errors import (EnosFailedHostsError,
                            EnosUnreachableHostsError,
                            EnosSSHNotReady)

logger = logging.getLogger(__name__)

COMMAND_NAME = u"enoslib_adhoc_command"
STATUS_OK = "OK"
STATUS_FAILED = "FAILED"
STATUS_UNREACHABLE = "UNREACHABLE"
STATUS_SKIPPED = "SKIPPED"
DEFAULT_ERROR_STATUSES = {STATUS_FAILED, STATUS_UNREACHABLE}

AnsibleExecutionRecord = namedtuple(
    'AnsibleExecutionRecord', ['host', 'status', 'task', 'payload'])


def _load_defaults(inventory_path=None, roles=None, extra_vars=None, tags=None,
                   basedir=False):
    """Load common defaults data structures.

    For factorization purpose."""

    extra_vars = extra_vars or {}
    tags = tags or []
    loader = DataLoader()
    if basedir:
        loader.set_basedir(basedir)

    inventory = EnosInventory(loader=loader,
                              sources=inventory_path, roles=roles)

    variable_manager = VariableManager(loader=loader,
                                       inventory=inventory)

    # seems mandatory to load group_vars variable
    if basedir:
        variable_manager.safe_basedir = True

    if extra_vars:
        variable_manager.extra_vars = extra_vars

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
                                     "check", "tags",
                                     "diff", "basedir"])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection="ssh",
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=None,
                      become_method="sudo", become_user="root",
                      remote_user=None, verbosity=2, check=False,
                      tags=tags, diff=None, basedir=basedir)

    return inventory, variable_manager, loader, options


class _MyCallback(CallbackModule):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'mycallback'

    def __init__(self, storage):
        super(_MyCallback, self).__init__()
        self.storage = storage
        self.display_ok_hosts = True
        self.display_skipped_hosts = True
        self.display_failed_stderr = True

    def _store(self, result, status):
        record = AnsibleExecutionRecord(
            host=result._host.get_name(), status=status,
            task=result._task.get_name(), payload=result._result)
        self.storage.append(record)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        super(_MyCallback, self).v2_runner_on_failed(result)
        self._store(result, STATUS_FAILED)

    def v2_runner_on_ok(self, result):
        super(_MyCallback, self).v2_runner_on_ok(result)
        self._store(result, STATUS_OK)

    def v2_runner_on_skipped(self, result):
        super(_MyCallback, self).v2_runner_on_skipped(result)
        self._store(result, STATUS_SKIPPED)

    def v2_runner_on_unreachable(self, result):
        super(_MyCallback, self).v2_runner_on_unreachable(result)
        self._store(result, STATUS_UNREACHABLE)


def run_play(play_source, inventory_path=None, roles=None,
             extra_vars=None, on_error_continue=False):
    """Run a play.

    Args:
        pattern_hosts (str): pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        play_source (dict): ansible task
        inventory_path (str): inventory to use
        extra_vars (dict): extra_vars to use
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``

    Returns:
        List of all the results
    """
    # NOTE(msimonin): inventory could be infered from a host list (maybe)
    results = []
    inventory, variable_manager, loader, options = _load_defaults(
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars)
    callback = _MyCallback(results)
    passwords = {}
    tqm = task_queue_manager.TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        options=options,
        passwords=passwords,
        stdout_callback=callback)

    # create play
    play_inst = play.Play().load(play_source,
                                 variable_manager=variable_manager,
                                 loader=loader)

    # actually run it
    try:
        tqm.run(play_inst)
    finally:
        tqm.cleanup()

    # Handling errors
    failed_hosts = []
    unreachable_hosts = []
    for r in results:
        if r.status == STATUS_UNREACHABLE:
            unreachable_hosts.append(r)
        if r.status == STATUS_FAILED:
            failed_hosts.append(r)

    if len(failed_hosts) > 0:
        logger.error("Failed hosts: %s" % failed_hosts)
        if not on_error_continue:
            raise EnosFailedHostsError(failed_hosts)
    if len(unreachable_hosts) > 0:
        logger.error("Unreachable hosts: %s" % unreachable_hosts)
        if not on_error_continue:
            raise EnosUnreachableHostsError(unreachable_hosts)

    return results


class play_on(object):
    """A context manager to manage a sequence of Ansible module calls."""
    def __init__(self, pattern_hosts,
                 inventory_path=None,
                 roles=None,
                 extra_vars=None,
                 on_error_continue=False,
                 gather_facts=True):
        """Constructor.

        Args:
            pattern_hosts (str): pattern to describe ansible hosts to target.
                see https://docs.ansible.com/ansible/latest/intro_patterns.html
            inventory_path (str): inventory to use
            roles (dict): equivalent to the inventory, but in memory
            extra_vars (dict): extra_vars to use
            on_error_continue(bool): Don't throw any exception in case a host
                is unreachable or the playbooks run with errors
            gather_facts (bool): Whether the facts of all hosts in roles (or
                the inventory file) must be collected.

        Example:

        .. code-block:: python

            with actions_on("all", roles=roles) as t:
                t.apt(name=["curl", "git"], state="present")
                t.shell("which docker || (curl get.docker.com | sh)")
                t.docker_container(name="nginx", state="started")

        Any ansible module can be called using the above way. You'll need to
        refer to the module reference documentation to find the corresponding
        kwargs to use. """
        self.pattern_hosts = pattern_hosts
        self.inventory_path = inventory_path
        self.roles = roles
        self.extra_vars = extra_vars
        self.on_error_continue = on_error_continue

        # Will hold the tasks of the play corresponding to the sequence
        # of module call in this context
        self._tasks = []

        # Handle gather_facts
        # if True we generate a first play to gather the facts
        self.prior = {}
        if gather_facts:
            self.prior = {
                "hosts": "all",
                "tasks": [{
                    "name": "Gathering Facts",
                    "setup": {"gather_subset": "all"}
                }]
            }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        play_source = {
            # we force the fact gathering on all hosts
            # There'll be some performance impact if caching isn't enable.
            "hosts": self.pattern_hosts,
            "tasks": self._tasks
        }
        logger.debug(play_source)

        # Generate a playbook and run it
        with tempfile.NamedTemporaryFile('w',
                                         buffering=1,
                                         dir=os.getcwd()) as _pb:
            _pb.write(yaml.dump([self.prior, play_source]))
            run_ansible([_pb.name],
                        roles=self.roles,
                        extra_vars=self.extra_vars,
                        on_error_continue=self.on_error_continue)

    def __getattr__(self, module_name):
        """Providers an handy way to use ansible module from python.

        """
        def _f(**kwargs):
            task = {}
            task.update(**kwargs)
            self._tasks.append({
                "name": "__calling__ %s" % module_name,
                module_name: task,
            })

        def _shell_like(command, **kwargs):
            self._tasks.append({
                "name": "__calling__ %s" % module_name,
                module_name: command,
                "args": dict(**kwargs),
            })

        if module_name in ["command", "shell"]:
            return _shell_like
        return _f


def run_command(pattern_hosts, command, inventory_path=None, roles=None,
                extra_vars=None,
                on_error_continue=False):
    """Run a shell command on some remote hosts.

    Args:
        pattern_hosts (str): pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        command (str): the command to run
        inventory_path (str): inventory to use
        extra_vars (dict): extra_vars to use
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``

    Returns:
        Dict combining the stdout and stderr of ok and failed hosts and every
        results of tasks executed (this may include the fact gathering tasks)

    Example:

    .. code-block:: python

        # Inventory
        [control1]
        enos-0
        [control2]
        enos-1

        # Python
        result = run_command("control*", "date", inventory)

        # Result
        {
            'failed': {},
            'ok':
            {
                u'enos-0':
                {
                    'stderr': u'',
                    'stdout': u'Tue Oct 31 04:53:04 GMT 2017'
                },
                u'enos-1':
                {
                    'stderr': u'',
                    'stdout': u'Tue Oct 31 04:53:05 GMT 2017'}
                },
            'results': [...]
        }

    If facts are gathers this is possible to use ansible templating

    .. code-block:: python

        result = run_command("control*", "ping -c 1
        {{hostvars['enos-1']['ansible_' + n1].ipv4.address}}", inventory)
    """

    def filter_results(results, status):
        _r = [r for r in results
              if r.status == status and r.task == COMMAND_NAME]
        s = dict([[r.host, {"stdout": r.payload.get("stdout"),
                            "stderr": r.payload.get("stderr")}]
                  for r in _r])
        return s

    play_source = {
        "hosts": pattern_hosts,
        "tasks": [{
            "name": COMMAND_NAME,
            "shell": command,
        }]
    }
    results = run_play(play_source,
                       inventory_path=inventory_path,
                       roles=roles,
                       extra_vars=extra_vars)
    ok = filter_results(results, STATUS_OK)
    failed = filter_results(results, STATUS_FAILED)
    return {"ok": ok, "failed": failed, "results": results}


def run_ansible(playbooks, inventory_path=None, roles=None, extra_vars=None,
        tags=None, on_error_continue=False, basedir='.'):
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

    inventory, variable_manager, loader, options = _load_defaults(
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars,
        tags=tags,
        basedir=basedir
    )
    passwords = {}
    for path in playbooks:
        logger.info("Running playbook %s with vars:\n%s" % (path, extra_vars))
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
            logger.error("Failed hosts: %s" % failed_hosts)
            if not on_error_continue:
                raise EnosFailedHostsError(failed_hosts)
        if len(unreachable_hosts) > 0:
            logger.error("Unreachable hosts: %s" % unreachable_hosts)
            if not on_error_continue:
                raise EnosUnreachableHostsError(unreachable_hosts)


def discover_networks(roles, networks, fake_interfaces=None,
                    fake_networks=None):
    """Checks the network interfaces on the nodes.

    This enables to auto-discover the mapping interface name <-> network role.
    Beware, this has a side effect on each Host in roles.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        networks (list): network list as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        fake_interfaces (list): names of optionnal dummy interfaces to create
        fake_networks (list): names of the roles to associate with the fake
            interfaces. Like reguilar network interfaces, the mapping will be
            added to the host vars. Internally this will be zipped with the
            fake_interfaces to produce the mapping.

    If the command is successful each host will be added some variables.
    Assuming that one network whose role is `mynetwork` has been declared, the
    following variables will be available through the ansible hostvars:

    - ``mynetwork=eth1``, `eth1` has been discovered has the interface in the
      network `mynetwork`.
    - ``mynetwork_dev=eth1``, same as above with a different accessor names
    - ``mynetwork_ip=192.168.42.42``, this indicates the ip in the network
      `mynetwork` for this node

    All of this variable can then be accessed by the other nodes through the
    hostvars: ``hostvars[remote_node]["mynetwork_ip"]``
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

    wait_ssh(roles)
    tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
    fake_interfaces = fake_interfaces or []
    fake_networks = fake_networks or []

    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    facts_file = os.path.join(tmpdir, 'facts.json')
    options = {
        'enos_action': 'check_network',
        'facts_file': facts_file,
        'fake_interfaces': fake_interfaces
    }
    run_ansible([utils_playbook], roles=roles,
        extra_vars=options,
        on_error_continue=False)

    # Read the file
    # Match provider networks to interface names for each host
    with open(facts_file) as f:
        facts = json.load(f)
        for _, host_facts in facts.items():
            host_nets = _map_device_on_host_networks(networks,
                                                    get_devices(host_facts))
            # Add the mapping : networks <-> nic name
            host_facts['networks'] = host_nets

    # Finally update the env with this information
    # generate the extra_mapping for the fake interfaces
    extra_mapping = dict(zip(fake_networks, fake_interfaces))
    _update_hosts(roles, facts, extra_mapping=extra_mapping)


def generate_inventory(roles, networks, inventory_path, check_networks=False,
                       fake_interfaces=None, fake_networks=None):
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
        fake_networks (list): names of the roles to associate with the fake
            interfaces. Like reguilar network interfaces, the mapping will be
            added to the host vars. Internally this will be zipped with the
            fake_interfaces to produce the mapping. """

    with open(inventory_path, "w") as f:
        f.write(_generate_inventory(roles))

    if check_networks:
        discover_networks(
            roles,
            networks,
            fake_interfaces=fake_interfaces,
            fake_networks=fake_networks
        )
        with open(inventory_path, "w") as f:
            f.write(_generate_inventory(roles))


def emulate_network(network_constraints,
                    roles=None,
                    inventory_path=None,
                    extra_vars=None):
    """Emulate network links.

    Read ``network_constraints`` and apply ``tc`` rules on all the nodes.
    Constraints are applied between groups of machines. Theses groups are
    described in the ``network_constraints`` variable and must be found in the
    inventory file. The newtwork constraints support ``delay``, ``rate`` and
    ``loss``.

    Args:
        network_constraints (dict): network constraints to apply
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory_path(string): path to an inventory
        extra_vars (dict): extra_vars to pass to ansible

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
            emulate_network(roles, tc)

        If you want to control more precisely which groups need to be taken
        into account, you can use ``except`` or ``groups`` key

        .. code-block:: python

            tc = {
                "enable": True,
                "default_delay": "20ms",
                "default_rate": "1gbit",
                "except": "grp3"
            }
            emulate_network(roles, tc)

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

    if not network_constraints:
        return

    if roles is None and inventory is None:
        raise ValueError("roles and inventory can't be None")

    if not extra_vars:
        extra_vars = {}

    # 1. getting  ips/devices information
    logger.debug('Getting the ips of all nodes')
    tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    ips_file = os.path.join(tmpdir, 'ips.txt')
    options = {'enos_action': 'tc_ips',
               'ips_file': ips_file}
    run_ansible([utils_playbook], roles=roles, extra_vars=options)

    # 2.a building the group constraints
    logger.debug('Building all the constraints')
    constraints = _build_grp_constraints(roles, network_constraints)
    # 2.b Building the ip/device level constaints
    with open(ips_file) as f:
        ips = yaml.safe_load(f)
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
    logger.info('Enforcing the constraints')
    # enabling/disabling network constraints
    enable = network_constraints.setdefault('enable', True)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {
        'enos_action': 'tc_apply',
        'ips_with_constraints': ips_with_constraints,
        'tc_enable': enable,
    }
    options.update(extra_vars)
    run_ansible([utils_playbook],
                roles=roles,
                inventory_path=inventory_path,
                extra_vars=options)


def validate_network(roles=None,
                     inventory_path=None,
                     output_dir=None,
                     extra_vars=None):
    """Validate the network parameters (latency, bandwidth ...)

    Performs flent, ping tests to validate the constraints set by
    :py:func:`emulate_network`. Reports are available in the tmp directory used
    by enos.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory_path (str): path to an inventory
        output_dir (str): directory where validation files will be stored.
            Default to :py:const:`enoslib.constants.TMP_DIRNAME`.
    """
    logger.debug('Checking the constraints')
    if not output_dir:
        output_dir = os.path.join(os.getcwd(), TMP_DIRNAME)

    if not extra_vars:
        extra_vars = {}

    output_dir = os.path.abspath(output_dir)
    _check_tmpdir(output_dir)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'enos_action': 'tc_validate',
               'tc_output_dir': output_dir}

    options.update(extra_vars)
    run_ansible([utils_playbook],
                roles=roles,
                inventory_path=inventory_path,
                extra_vars=options)


def reset_network(roles, extra_vars=None):
    """Reset the network constraints (latency, bandwidth ...)

    Remove any filter that have been applied to shape the traffic.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inventory (str): path to the inventory
    """
    logger.debug('Reset the constraints')

    if not extra_vars:
        extra_vars = {}

    tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)

    _check_tmpdir(tmpdir)
    utils_playbook = os.path.join(ANSIBLE_DIR, 'utils.yml')
    options = {'enos_action': 'tc_reset',
               'tc_output_dir': tmpdir}
    options.update(extra_vars)
    run_ansible([utils_playbook], roles=roles, extra_vars=options)


def wait_ssh(roles, retries=100, interval=30):
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
                        roles=roles,
                        extra_vars=options,
                        on_error_continue=False)
            break
        except EnosUnreachableHostsError as e:
            logger.info("Hosts unreachable: %s " % e.hosts)
            logger.info("Retrying... %s/%s" % (i + 1, retries))
            time.sleep(interval)
    else:
        raise EnosSSHNotReady('Maximum retries reached')


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
        s = int(m.group('start'))
        e = int(m.group('end'))
        n = m.group('name')
        return list(map(lambda x: n + str(x), range(s, e + 1)))
    else:
        return [grp]


# Private zone
def _generate_inventory(roles):
    """Generates an inventory files from roles

    :param roles: dict of roles (roles -> list of Host)
    """
    inventory = EnosInventory(roles=roles)
    return inventory.to_ini_string()


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
            host.extra.update(extra_mapping)
            for network in networks:
                device = network['device']
                if device:
                    for role in get_roles_as_list(network):
                        # backward compatibility:
                        # network_role=eth_name
                        host.extra.update({role: device})
                        # we introduce some shortcuts (avoid infinite ansible
                        # templates) in other words, we sort of precompute them
                        # network_role_dev=eth_name
                        # network_role_ip=ip
                        #
                        # Use case:
                        # - node1 has eth1 for role: r1,
                        # - node2 has eth2 for role: r2
                        # the conf in node2 must point to the ip of eth1 in
                        # node1 node2 can use hostvars[node1].r1_ip as a
                        # template Note this can happen often in g5k between
                        # nodes of different clusters
                        host.extra.update({'%s_dev' % role: device})
                        key = 'ansible_%s' % device
                        ip = facts[host.alias][key]['ipv4']['address']
                        host.extra.update({'%s_ip' % role: ip})

                    enos_devices.append(device)

            # Add the list of devices in used by Enos
            host.extra.update({'enos_devices': enos_devices})


def _expand_description(desc):
    """Expand the description given the group names/patterns
    e.g:
    {src: grp[1-3], dst: grp[4-6] ...} will generate 9 descriptions
    """
    srcs = expand_groups(desc['src'])
    dsts = expand_groups(desc['dst'])
    descs = []
    for src in srcs:
        for dst in dsts:
            local_desc = desc.copy()
            local_desc['src'] = src
            local_desc['dst'] = dst
            descs.append(local_desc)

    return descs


def _src_equals_dst_in_constraints(network_constraints, grp1):
    if 'constraints' in network_constraints:
        constraints = network_constraints['constraints']
        for desc in constraints:
            descs = _expand_description(desc)
            for d in descs:
                if grp1 == d['src'] and d['src'] == d['dst']:
                    return True
    return False


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
    grps = [expand_groups(g) for g in grps]
    # flatten
    grps = [x for expanded_group in grps for x in expanded_group]
    # building the default group constraints
    return [{'src': grp1,
             'dst': grp2,
             'delay': default_delay,
             'rate': default_rate,
             'loss': default_loss}
            for grp1 in grps for grp2 in grps
            if ((grp1 != grp2
                 or _src_equals_dst_in_constraints(network_constraints, grp1))
                and grp1 not in except_groups and grp2 not in except_groups)]


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
            # Get only the devices specified in the network constraint
            if 'network' in constraint:
                active_devices = filter(
                    lambda x:
                    x['device'] == s.extra[constraint['network']],
                    active_devices)
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
