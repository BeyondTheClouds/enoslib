# -*- coding: utf-8 -*-
from collections import namedtuple
import copy
import logging
import os
import tempfile
from typing import Any, List, MutableMapping, Mapping, Optional, Union
import time
import json
import yaml


# These two imports are 2.9
from ansible.module_utils.common.collections import ImmutableDict
from ansible import context
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
from enoslib.errors import (
    EnosFailedHostsError,
    EnosUnreachableHostsError,
    EnosSSHNotReady,
)
from enoslib.types import Roles, Networks

logger = logging.getLogger(__name__)

COMMAND_NAME = "enoslib_adhoc_command"
STATUS_OK = "OK"
STATUS_FAILED = "FAILED"
STATUS_UNREACHABLE = "UNREACHABLE"
STATUS_SKIPPED = "SKIPPED"
DEFAULT_ERROR_STATUSES = {STATUS_FAILED, STATUS_UNREACHABLE}
# The following translate the keywords passed in the play_on tasks to
# actual ansible keywords. We do that because async became a reserved keyword
# in python3.7 so on can't write :
# with play_on() as p
#   p.shell(..., async=100)
# But rather will need to write (with an h!)
# with play_on() as p
#   p.shell(..., asynch=100)
ANSIBLE_TOP_LEVEL = {
    "asynch": "async",
    "become": "become",
    "become_user": "become_user",
    "become_method": "become_method",
    "loop": "loop",
    "poll": "poll",
    "ignore_errors": "ignore_errors",
    "environment": "environment",
}

AnsibleExecutionRecord = namedtuple(
    "AnsibleExecutionRecord", ["host", "status", "task", "payload"]
)


def _split_args(**kwargs):
    """Splits top level kwargs and module specific kwargs."""
    top_args = {}
    module_args = {}
    for k, v in kwargs.items():
        if k in ANSIBLE_TOP_LEVEL.keys():
            top_args.update({ANSIBLE_TOP_LEVEL[k]: v})
        else:
            module_args.update({k: v})
    return top_args, module_args


def _load_defaults(
    inventory_path=None, roles=None, extra_vars=None, tags=None, basedir=False
):
    """Load common defaults data structures.

    For factorization purpose."""

    extra_vars = extra_vars or {}
    tags = tags or []
    loader = DataLoader()
    if basedir:
        loader.set_basedir(basedir)

    inventory = EnosInventory(loader=loader, sources=inventory_path, roles=roles)

    variable_manager = VariableManager(loader=loader, inventory=inventory)

    # seems mandatory to load group_vars variable
    if basedir:
        variable_manager.safe_basedir = True

    if extra_vars:
        # 2.9: we hack this, normally extra_vars are loaded from the
        # context.CLIARGS.extra_vars that can be loaded from the cli, or a file,..
        # self._extra_vars = load_extra_vars(loader=self._loader)
        # in variable manager constructor
        variable_manager._extra_vars = extra_vars

    # NOTE(msimonin): The ansible api is "low level" in the
    # sense that we are redefining here all the default values
    # that are usually enforce by ansible called from the cli
    context.CLIARGS = ImmutableDict(
        start_at_task=None,
        listtags=False,
        listtasks=False,
        listhosts=False,
        syntax=False,
        connection="ssh",
        module_path=None,
        forks=100,
        private_key_file=None,
        ssh_common_args=None,
        ssh_extra_args=None,
        sftp_extra_args=None,
        scp_extra_args=None,
        become=None,
        become_method="sudo",
        become_user="root",
        remote_user=None,
        verbosity=2,
        check=False,
        tags=tags,
        diff=None,
        basedir=basedir,
    )

    return inventory, variable_manager, loader


class _MyCallback(CallbackModule):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "mycallback"

    def __init__(self, storage):
        super(_MyCallback, self).__init__()
        self.storage = storage
        self.display_ok_hosts = True
        self.display_skipped_hosts = True
        self.display_failed_stderr = True
        # since 2.9
        self.set_option("show_per_host_start", True)

    def _store(self, result, status):
        record = AnsibleExecutionRecord(
            host=result._host.get_name(),
            status=status,
            task=result._task.get_name(),
            payload=result._result,
        )
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


def run_play(
    play_source,
    *,
    inventory_path=None,
    roles=None,
    extra_vars=None,
    on_error_continue=False,
):
    """Run a play.

    Args:
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
    logger.debug(play_source)
    print(extra_vars)
    results = []
    inventory, variable_manager, loader = _load_defaults(
        inventory_path=inventory_path, roles=roles, extra_vars=extra_vars
    )
    callback = _MyCallback(results)
    passwords = {}
    tqm = task_queue_manager.TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords,
        stdout_callback=callback,
    )

    # create play
    play_inst = play.Play().load(
        play_source, variable_manager=variable_manager, loader=loader
    )

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

    def __init__(
        self,
        *,
        pattern_hosts: str = "all",
        inventory_path: Optional[str] = None,
        roles: Optional[Roles] = None,
        extra_vars: Optional[MutableMapping[Any, Any]] = None,
        on_error_continue: bool = False,
        gather_facts: Union[str, bool] = True,
        priors: Optional[List["play_on"]] = None,
        run_as: Optional[str] = None,
    ):
        """Constructor.

        Args:
            pattern_hosts: pattern to describe ansible hosts to target.
                see https://docs.ansible.com/ansible/latest/intro_patterns.html
            inventory_path: inventory to use
            roles: roles as returned by :py:meth:`enoslib.infra.provider.Provider.init`
            extra_vars: extra_vars to use
            on_error_continue: don't throw any exception in case a host
                is unreachable or the playbooks run with errors
            gather_facts: controls how the facts will be gathered.
                - True    -> Gathers facts of :py:attr:`pattern_hosts` hosts.
                - False   -> Does not gather facts.
                - pattern -> Gathers facts of `pattern` hosts.
            priors: tasks in each prior will be prepended in the playbook
            run_as: A shortcut that injects become and become_user to each task.
                    become* at the task level has the precedence over this parameter


        Examples:

            - Minimal snippet:

                .. code-block:: python

                    with play_on(roles=roles) as t:
                        t.apt(name=["curl", "git"], state="present")
                        t.shell("which docker || (curl get.docker.com | sh)")
                        t.docker_container(name="nginx", state="started")

            - Complete example with fact_gathering

                .. literalinclude:: examples/run_play_on.py
                    :language: python
                    :linenos:

        Hint
            - Module can be run asynchronously using the corresponding Ansible options
              Note that not all the modules support asynchronous execution.

            - Note that the actual result isn't available in the result file but will
              be available through a file specified in the result object.

            - Any ansible module can be called using the above way. You'll need to
              refer to the module reference documentation to find the corresponding
              kwargs to use.
        """
        self.pattern_hosts = pattern_hosts
        self.inventory_path = inventory_path
        self.roles = roles
        self.extra_vars = extra_vars if extra_vars is not None else {}
        self.on_error_continue = on_error_continue
        self.priors = priors if priors is not None else []

        # Handle modification of task level kwargs
        if run_as is not None:
            self.kwds = dict(become=True, become_user=run_as)
        else:
            self.kwds = {}

        # Will hold the tasks of the play corresponding to the sequence
        # of module call in this context
        self._tasks: List[Mapping[Any, Any]] = []
        if self.priors:
            for prior in self.priors:
                self._tasks.extend(prior._tasks)

        # Handle gather_facts
        self.gather_facts = gather_facts

    def __enter__(self):
        return self

    def __exit__(self, *args):
        gather_source = dict(hosts=[], gather_facts=False, tasks=[])
        play_source = dict(
            hosts=self.pattern_hosts, tasks=self._tasks, gather_facts=False
        )

        if isinstance(self.gather_facts, str):
            gather_source.update(hosts=self.gather_facts, gather_facts=True)
            playbook = [gather_source, play_source]
        elif self.gather_facts:
            gather_source.update(hosts=self.pattern_hosts, gather_facts=True)
            playbook = [gather_source, play_source]
        else:
            gather_source.update(gather_facts=False)
            playbook = [play_source]

        logger.debug(playbook)

        # Generate a playbook and run it
        with tempfile.NamedTemporaryFile("w", buffering=1, dir=os.getcwd()) as _pb:
            content = yaml.dump(playbook)
            _pb.write(content)
            logger.debug("Generated playbook")
            logger.debug(content)
            run_ansible(
                [_pb.name],
                roles=self.roles,
                extra_vars=self.extra_vars,
                on_error_continue=self.on_error_continue,
            )

    def __getattr__(self, module_name):
        """Providers an handy way to use ansible module from python.

        """

        def _f(**kwargs):
            display_name = kwargs.pop("display_name", "__calling__ %s" % module_name)
            task = {"name": display_name}
            _kwds = copy.copy(self.kwds)
            _kwds.update(kwargs)
            top_args, module_args = _split_args(**_kwds)
            task.update(top_args)
            task.update({module_name: module_args})
            self._tasks.append(task)

        def _shell_like(command, **kwargs):
            display_name = kwargs.pop("display_name", command)
            task = {"name": display_name, module_name: command}
            _kwds = copy.copy(self.kwds)
            _kwds.update(kwargs)
            top_args, module_args = _split_args(**_kwds)
            task.update(top_args)
            if module_args:
                task.update(args=module_args)
            self._tasks.append(task)

        if module_name in ["command", "shell", "raw"]:
            return _shell_like
        return _f


# can be used as prior
__python3__ = play_on(roles={})
__python3__.raw(
    (
        "(python --version | grep --regexp ' 3.*')"
        "||"
        "(apt update && apt install -y python3 python3-pip)"
    ),
    display_name="Install python3",
)
__default_python3__ = play_on(roles={})
__default_python3__.raw(
    "update-alternatives --install /usr/bin/python python /usr/bin/python3 1",
    display_name="Making python3 the default python interpreter",
)


__python2__ = play_on(roles={})
__python2__.raw(
    (
        "(python --version | grep --regexp ' 2.*')"
        "||"
        "(apt update && apt install -y python python-pip)"
    ),
    display_name="Install python2",
)
__default_python2__ = play_on(roles={})
__default_python2__.raw(
    "update-alternatives --install /usr/bin/python python /usr/bin/python2 1"
)


__docker__ = play_on(roles={})
__docker__.shell("which docker || (curl -sSL https://get.docker.com/ | sh)")


def ensure_python3(make_default=True, **kwargs):
    """Make sure python3 is installed on the remote nodes and is the default.

    It inherits the arguments of :py:class:`enoslib.api.play_on`.
    """
    kwargs.pop("priors", None)
    kwargs.pop("gather_facts", None)
    priors = [__python3__]
    if make_default:
        priors.append(__default_python3__)
    with play_on(priors=priors, gather_facts=False, **kwargs) as p:
        p.raw("hostname")


def ensure_python2(make_default=True, **kwargs):
    """Make sure python is installed on the remote nodes and is the default.

    It inherits the arguments of :py:class:`enoslib.api.play_on`.
    """
    kwargs.pop("priors", None)
    kwargs.pop("gather_facts", None)
    priors = [__python2__]
    if make_default:
        priors.append(__default_python2__)
    with play_on(priors=priors, gather_facts=False, **kwargs) as p:
        p.raw("hostname")


def run_command(
    command: str,
    *,
    pattern_hosts: str = "all",
    inventory_path: Optional[str] = None,
    roles: Optional[Roles] = None,
    extra_vars: Optional[Mapping] = None,
    on_error_continue: bool = False,
    run_as: Optional[str] = None,
    **kwargs: Any,
):
    """Run a shell command on some remote hosts.

    Args:
        command (str): the command to run
        pattern_hosts (str): pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        inventory_path (str): inventory to use
        roles (dict): the roles to use (replacement for inventory_path).
        extra_vars (dict): extra_vars to use
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors
        run_as(str): run the command as this user.
            This is equivalent to passing become=yes and become_user=user but
            become_method can be passed to modify the priviledge escalation
            method. (default to sudo).
        kwargs: keywords argument to pass to the shell module or as top level
            args.

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
        result = run_command("date", inventory)

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

    If facts are gathered it is possible to use ansible templating

    .. code-block:: python

        result = run_command("control*", "ping -c 1
        {{hostvars['enos-1']['ansible_' + n1].ipv4.address}}", inventory)


    Command can be run asynchronously using the corresponding Ansible options
    (see https://docs.ansible.com/ansible/latest/user_guide/playbooks_async.html)

    .. code-block:: python

        result = run_command("date", roles=roles, async=20, poll=0)

    Note that the actual result isn't available in the result file but will be
    available through a file specified in the result object. """

    def filter_results(results, status):
        _r = [r for r in results if r.status == status and r.task == COMMAND_NAME]
        s = dict(
            [
                [
                    r.host,
                    {
                        "stdout": r.payload.get("stdout"),
                        "stderr": r.payload.get("stderr"),
                    },
                ]
                for r in _r
            ]
        )
        return s

    if run_as is not None:
        # run_as is a shortcut
        kwargs.update(become=True, become_user=run_as)

    task = {"name": COMMAND_NAME, "shell": command}

    top_args, module_args = _split_args(**kwargs)
    task.update(top_args)
    task.update(args=module_args)

    play_source = {"hosts": pattern_hosts, "tasks": [task]}

    results = run_play(
        play_source, inventory_path=inventory_path, roles=roles, extra_vars=extra_vars
    )
    ok = filter_results(results, STATUS_OK)
    failed = filter_results(results, STATUS_FAILED)
    return {"ok": ok, "failed": failed, "results": results}


def run(command, hosts, extra_vars=None, on_error_continue=False, **kwargs):
    """Run a shell command on some remote hosts.

        This is a wrapper of :py:func:`enoslib.api.run_command`.
    """

    return run_command(
        command,
        roles={"all": hosts},
        extra_vars=extra_vars,
        on_error_continue=on_error_continue,
        **kwargs,
    )


def gather_facts(
    *,
    pattern_hosts="all",
    gather_subset="all",
    inventory_path=None,
    roles=None,
    extra_vars=None,
    on_error_continue=False,
):
    """Gather facts about hosts.


    This function can be used to check/save the information of the
    infrastructure where the experiment ran. It'll give the information
    gathered by Ansible (see
    https://docs.ansible.com/ansible/latest/user_guide/playbooks_variables.html
    )

    Args:
        pattern_hosts (str): pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        gather_subset (str): if supplied, restrict the additional facts
            collected to the given subset.
            https://docs.ansible.com/ansible/latest/modules/setup_module.html
        inventory_path (str): inventory to use
        roles (dict): the roles to use (replacement for inventory_path).
        extra_vars (dict): extra_vars to use
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``

    Returns:
        Dict combining the ansible facts of ok and failed hosts and every
        results of tasks executed.

    Example:

    .. code-block:: python

        # Inventory
        [control1]
        enos-0
        [control2]
        enos-1

        # Python
        result = gather_facts(roles=roles)

        # Result
        {
            'failed': {},
            'ok':
            {
              'enos-0':
              {
                'ansible_product_serial': 'NA',
                'ansible_form_factor': 'Other',
                'ansible_user_gecos': 'root',
                ...
              },
              'enos-1':
              {...}
            'results': [...]
        }

    """

    def filter_results(results, status):
        _r = [r for r in results if r.status == status and r.task == COMMAND_NAME]
        s = dict([[r.host, r.payload.get("ansible_facts")] for r in _r])
        return s

    play_source = {
        "hosts": pattern_hosts,
        "tasks": [{"name": COMMAND_NAME, "setup": {"gather_subset": gather_subset}}],
    }
    results = run_play(
        play_source,
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars,
        on_error_continue=on_error_continue,
    )
    ok = filter_results(results, STATUS_OK)
    failed = filter_results(results, STATUS_FAILED)

    return {"ok": ok, "failed": failed, "results": results}


def run_ansible(
    playbooks,
    inventory_path=None,
    roles=None,
    extra_vars=None,
    tags=None,
    on_error_continue=False,
    basedir=".",
):
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

    inventory, variable_manager, loader = _load_defaults(
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars,
        tags=tags,
        basedir=basedir,
    )
    passwords = {}
    for path in playbooks:
        logger.info("Running playbook %s with vars:\n%s" % (path, extra_vars))
        pbex = PlaybookExecutor(
            playbooks=[path],
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            passwords=passwords,
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


def discover_networks(
    roles: Roles,
    networks: Networks,
    fake_interfaces: List[str] = None,
    fake_networks: List[str] = None,
) -> Roles:
    """Checks the network interfaces on the nodes.

    This enables to auto-discover the mapping interface name <-> network role.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        networks (list): network list as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        fake_interfaces (list): names of optionnal dummy interfaces to create
        fake_networks (list): names of the roles to associate with the fake
            interfaces. Like regular network interfaces, the mapping will be
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
        for interface in facts["ansible_interfaces"]:
            ansible_interface = "ansible_" + interface
            # filter here (active/ name...)
            if "ansible_" + interface in facts:
                interface = facts[ansible_interface]
                devices.append(interface)
        return devices

    wait_ssh(roles)
    tmpdir = os.path.join(os.getcwd(), TMP_DIRNAME)
    _check_tmpdir(tmpdir)
    fake_interfaces = fake_interfaces or []
    fake_networks = fake_networks or []

    utils_playbook = os.path.join(ANSIBLE_DIR, "utils.yml")
    facts_file = os.path.join(tmpdir, "facts.json")
    options = {
        "enos_action": "check_network",
        "facts_file": facts_file,
        "fake_interfaces": fake_interfaces,
    }
    run_ansible(
        [utils_playbook], roles=roles, extra_vars=options, on_error_continue=False
    )

    # Read the file
    # Match provider networks to interface names for each host
    with open(facts_file) as f:
        facts = json.load(f)
        for _, host_facts in facts.items():
            host_nets = _map_device_on_host_networks(networks, get_devices(host_facts))
            # Add the mapping : networks <-> nic name
            host_facts["networks"] = host_nets

    # Finally update the env with this information
    # generate the extra_mapping for the fake interfaces
    extra_mapping = dict(zip(fake_networks, fake_interfaces))
    return _update_hosts(roles, facts, extra_mapping=extra_mapping)


def generate_inventory(
    roles,
    networks,
    inventory_path,
    check_networks=False,
    fake_interfaces=None,
    fake_networks=None,
):
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
        _roles = discover_networks(
            roles,
            networks,
            fake_interfaces=fake_interfaces,
            fake_networks=fake_networks,
        )
        with open(inventory_path, "w") as f:
            f.write(_generate_inventory(_roles))


def wait_ssh(roles: Roles, retries: int = 100, interval: int = 30) -> None:
    """Wait for all the machines to be ssh-reachable

    Let ansible initiates a communication and retries if needed.

    Args:
        roles: Roles to wait for
        retries: Number of time we'll be retrying an SSH connection
        interval: Interval to wait in seconds between two retries
    """
    for i in range(0, retries):
        try:
            with play_on(roles=roles, gather_facts=False, on_error_continue=False) as p:
                # We use the raw module because we can't assumed at this point that
                # python is installed
                p.raw("hostname")
            break
        except EnosUnreachableHostsError as e:
            logger.info("Hosts unreachable: %s " % e.hosts)
            logger.info("Retrying... %s/%s" % (i + 1, retries))
            time.sleep(interval)
    else:
        raise EnosSSHNotReady("Maximum retries reached")


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
    _roles = copy.deepcopy(roles)
    extra_mapping = extra_mapping or {}
    for hosts in _roles.values():
        for host in hosts:
            networks = facts[host.alias]["networks"]
            enos_devices = []
            host.extra.update(extra_mapping)
            for network in networks:
                device = network["device"]
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
                        host.extra.update({"%s_dev" % role: device})
                        key = "ansible_%s" % device
                        ip = facts[host.alias][key]["ipv4"]["address"]
                        host.extra.update({"%s_ip" % role: ip})

                    enos_devices.append(device)

            # Add the list of devices in used by Enos
            host.extra.update({"enos_devices": enos_devices})
    return _roles


def _map_device_on_host_networks(provider_nets, devices):
    """Decorate each networks with the corresponding nic name."""
    networks = copy.deepcopy(provider_nets)
    for network in networks:
        for device in devices:
            network.setdefault("device", None)
            ip_set = IPSet([network["cidr"]])
            if "ipv4" not in device:
                continue
            ips = device["ipv4"]
            if not isinstance(ips, list):
                ips = [ips]
            if len(ips) < 1:
                continue
            ip = IPAddress(ips[0]["address"])
            if ip in ip_set:
                network["device"] = device["device"]
                continue
    return networks
