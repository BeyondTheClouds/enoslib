"""Need to run some actions on your nodes ? This module is tailored for this
purpose.

Remote actions rely heavily on Ansible [#a1]_ used as a library through its
python API. Among other things a convenient context manager is brought to the
experimenter (see :py:class:`play_on`) to run arbitrary Ansible code without
leaving the python world.

These function can be fed with library-level objects (see :ref:`objects
<objects>`) and are thus provider agnostic.

.. topic:: Links

    .. [#a1] https://docs.ansible.com/ansible/latest/index.html

"""
from abc import ABCMeta, abstractmethod
import copy
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import os
import signal
from tempfile import NamedTemporaryFile, TemporaryDirectory
import time
import warnings
from collections import defaultdict, namedtuple
from pathlib import Path
import sys
from typing import Any, Dict, Sequence, List, Mapping, Optional, Set, Tuple

# These two imports are 2.9
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.module_utils.common.collections import ImmutableDict

# Note(msimonin): PRE 2.4 is
# from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.callback import CallbackBase

# Note(msimonin): PRE 2.4 is
# from ansible.vars import VariableManager
from ansible.vars.manager import VariableManager
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from rich.status import Console, Status

from ansible import context

from enoslib.config import get_config
from enoslib.constants import ANSIBLE_DIR
from enoslib.enos_inventory import EnosInventory
from enoslib.errors import (
    EnosFailedHostsError,
    EnosSSHNotReady,
    EnosUnreachableHostsError,
)
from enoslib.html import (
    convert_to_html_table,
    html_from_dict,
    html_from_sections,
    repr_html_check,
)
from enoslib.objects import Host, Networks, Roles, RolesLike
from enoslib.utils import _hostslike_to_roles

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
ONE_YEAR_SECONDS = 3600 * 24 * 365
ANSIBLE_TOP_LEVEL = {
    "asynch": "async",
    "become": "become",
    "become_user": "become_user",
    "become_method": "become_method",
    "environment": "environment",
    "ignore_errors": "ignore_errors",
    "loop": "loop",
    "poll": "poll",
    "when": "when",
    "run_once": "run_once",
    "delegate_to": "delegate_to",
    "background": {"async": ONE_YEAR_SECONDS, "poll": 0},
    "vars": "vars",
}


def _split_args(**kwargs):
    """Splits top level kwargs and module specific kwargs."""
    top_args = {}
    module_args = {}
    for k, v in kwargs.items():
        if k in ANSIBLE_TOP_LEVEL.keys():
            replacement = ANSIBLE_TOP_LEVEL[k]
            if isinstance(replacement, str):
                top_args.update({ANSIBLE_TOP_LEVEL[k]: v})
            elif isinstance(replacement, dict):
                top_args.update(**replacement)
            else:
                raise ValueError(f"No replacement candidate for keyword {k}")
        else:
            module_args.update({k: v})
    return top_args, module_args


def _load_defaults(
    inventory_path=None, roles=None, extra_vars=None, tags=None, basedir=False
):
    """Load common defaults data structures.

    For factorization purpose."""

    extra_vars = extra_vars or {}
    # inject python3
    if extra_vars.get("ansible_python_interpreter") is None:
        extra_vars.update(ansible_python_interpreter="python3")

    logger.debug(f"Using extra_vars = {extra_vars}")
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
        become=False,
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


_AnsibleExecutionRecord = namedtuple(
    "_AnsibleExecutionRecord", ["host", "status", "task", "payload"]
)


class HostStatus(Enum):
    NEUTRAL = "%s"
    FAILED = "[red]%s[/red]"
    OK = "[green]%s[/green]"
    UNREACHABLE = "[orange]%s[/orange]"
    SKIPPED = "[blue]%s[/blue]"


@dataclass(unsafe_hash=True)
class HostWithStatus:
    name: str = field(compare=True, hash=True)
    status: HostStatus = field(compare=False, default=HostStatus.NEUTRAL, hash=False)

    def set_status(self, status: HostStatus):
        self.status = status

    def rich(self):
        return self.status.value % self.name


class NoopCallback(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_NAME = "noop"
    CALLBACK_TYPE = "stdout"


class SpinnerCallback(CallbackBase):
    """Spinning during tasks execution.


    Design goals:
        - compatible with linear/free execution strategy
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_NAME = "spinner"
    CALLBACK_TYPE = "stdout"

    def __init__(self):
        super().__init__()
        self.running_tasks = defaultdict(dict)
        self.console = Console()
        self.status = None
        self.tasks_lst = []

    def v2_runner_on_start(self, host, task):
        """
        Misc notes:
        in the free strategy there's no notion of current task
        if the task doesn't exist add a description + initial list of host
            update the spinner
        if the task exist, add the host (free strategy case // slow hosts)
            update the spinner
        """
        task_name = task.get_name()
        if task_name not in self.tasks_lst:
            self.tasks_lst.append(task_name)
        self.running_tasks[task_name][host.name] = HostStatus.NEUTRAL
        self.update(task_name)

    def update(self, task_name):
        # fire a new spinner if it doesn't exist
        if self.status is None:
            self.status = Status("", console=self.console)
            self.status.start()
        hosts_status = self.running_tasks[task_name]
        status_str = " ".join(
            [status.value % host for (host, status) in hosts_status.items()]
        )
        self.status.update(
            f"[bold blue]Running[/bold blue] [magenta]{task_name}[/magenta] "
            f"on {status_str}"
        )

    def v2_runner_on_failed(self, result, ignore_errors=False):
        if not ignore_errors:
            status = HostStatus.FAILED
        else:
            status = HostStatus.OK
        self.running_tasks[result.task_name][result._host.name] = status
        self.update(result.task_name)

    def v2_runner_on_ok(self, result, ignore_errors=False):
        self.running_tasks[result.task_name][result._host.name] = HostStatus.OK
        self.update(result.task_name)

    def v2_runner_on_unreachable(self, result):
        self.running_tasks[result.task_name][result._host.name] = HostStatus.UNREACHABLE
        self.update(result.task_name)

    def v2_runner_on_skipped(self, result):
        self.running_tasks[result.task_name][result._host.name] = HostStatus.SKIPPED
        self.update(result.task_name)

    def v2_playbook_on_stats(self, stats):
        if self.status:
            self.status.stop()
        tasks_str = ",".join(self.tasks_lst)
        self.console.print(
            f"[bold blue]Finished {len(self.running_tasks)} tasks[/bold blue] "
            f"[italic]({tasks_str})[/italic]"
        )
        self.console.rule()


class _MyCallback(CallbackBase):

    CALLBACK_VERSION = 2.0
    CALLBACK_NAME = "mycallback"

    def __init__(self, storage):
        super().__init__()
        self.storage = storage
        self.display_ok_hosts = True
        self.display_skipped_hosts = True
        self.display_failed_stderr = True
        # since 2.9
        self.set_option("show_per_host_start", True)

    def _store(self, result, status):
        record = _AnsibleExecutionRecord(
            host=result._host.get_name(),
            status=status,
            task=result._task.get_name(),
            payload=result._result,
        )
        self.storage.append(record)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        super().v2_runner_on_failed(result)
        if not ignore_errors:
            self._store(result, STATUS_FAILED)
        else:
            self._store(result, STATUS_OK)

    def v2_runner_on_ok(self, result):
        super().v2_runner_on_ok(result)
        self._store(result, STATUS_OK)

    def v2_runner_on_skipped(self, result):
        super().v2_runner_on_skipped(result)
        self._store(result, STATUS_SKIPPED)

    def v2_runner_on_unreachable(self, result):
        super().v2_runner_on_unreachable(result)
        self._store(result, STATUS_UNREACHABLE)


@dataclass
class BaseCommandResult:
    # mypy https://github.com/python/mypy/issues/5374
    __metaclass__ = ABCMeta
    host: str
    task: str
    status: str
    payload: Dict

    @abstractmethod
    def _payload_keys(self):
        ...

    def ok(self):
        return self.status == STATUS_OK

    def match(self, **kwargs):
        for k, v in kwargs.items():
            attr_value = getattr(self, k)
            if attr_value != v:
                return False
        return True

    @repr_html_check
    def _repr_html_(self, content_only=False):
        return html_from_dict(
            str(self.__class__), self.__dict__, content_only=content_only
        )

    def _summarize(self):
        p = {
            k: self.payload[k]
            for k in self._payload_keys()
            if self.payload.get(k) is not None
        }
        if not p:
            p = f"[{sys.getsizeof(self.payload)} bytes]"
        return dict(
            host=self.host,
            task=self.task,
            status=self.status,
            payload=p,
        )

    @staticmethod
    def from_play(play_result: _AnsibleExecutionRecord) -> "BaseCommandResult":
        if "ansible_job_id" in play_result.payload:
            return AsyncCommandResult(**play_result._asdict())
        if "rc" in play_result.payload:
            return CommandResult(**play_result._asdict())

        return CustomCommandResult(**play_result._asdict())

    def __getattr__(self, name: str) -> Any:
        """missing method."""
        if name not in self._payload_keys():
            raise AttributeError()
        return self.payload.get(name)

    def to_dict(self, include_payload: bool = False) -> Dict:
        """A representation as a Dict.

        Use case: json serialization

        Args:
            include_payload: True wheter the payload must be included.

        Returns:
            A dict representing the object
        """
        d = {name: self.payload.get(name) for name in self._payload_keys()}
        if include_payload:
            d.update(payload=self.payload)
        return dict(host=self.host, task=self.task, status=self.status, **d)


class CommandResult(BaseCommandResult):
    def _payload_keys(self):
        return ["stdout", "stderr", "rc"]


class AsyncCommandResult(BaseCommandResult):
    def _payload_keys(self):
        return ["results_file", "ansible_job_id"]


class CustomCommandResult(BaseCommandResult):
    def _payload_keys(self):
        return []


class Results(list):
    """Container for CommandResult**s**

    Running one (or more) command(s) on several hosts leads to multiple results
    to be gathered by EnOSlib.
    EnOSlib manage the results as a flat list of individual result (one per host
    and command) but allow for some filtering to be done.

    Examples:

        .. code-block:: python

            result = en.run_command("date", roles=roles)
            # print the stdout of foo-1
            print(result.filter(host="foo-1").stdout)

            # get all the stderr of ko tasks (note the plural form)
            print(result.filter(status=STATUS_FAILED).stderrs)
    """

    def filter(self, **kwargs):
        return Results([c for c in self if c.match(**kwargs)])

    def ok(self, **kwargs):
        return Results([c for c in self if c.ok()])

    @repr_html_check
    def _repr_html_(self, content_only=False):
        return html_from_sections(
            str(self.__class__),
            convert_to_html_table([d._summarize() for d in self]),
            content_only=content_only,
        )

    def to_dict(self, include_payload: bool = False) -> List[Dict]:
        """A dict representation of a Results

        Use case: JSON serialization

        Args:
            include_payload: True wheter the raw payload must be included.

        Returns:
            A list of the dict, each element represents one Result.
        """
        return [r.to_dict(include_payload=include_payload) for r in self]

    @staticmethod
    def from_ansible(results: List[_AnsibleExecutionRecord]):
        return Results(BaseCommandResult.from_play(r) for r in results)


def populate_keys(
    roles: RolesLike, local_dir: Path, key_name="id_rsa_enoslib"
) -> Tuple[Path, Path]:
    """Generate and push a new pair of keys to all hosts.

    Idempotency:
    - a new pair of keys is generated/published every time you call this
      function (* as a first step)
    - the remote key are named with a name that doesn't conflict with any of
      the common key names (we don't want to overwrite any existing keys).
    - the public key is appended to the `authorized_keys` of root user

    Args:
        roles: The roles on which this should be applied
        local_dir: The local destination folder where the keys will be generated
        key_name: The key pair name, .pub will be added as a suffix for the
            public one

    Returns:
        The path to the key files as a Tuple (private, public)
    """
    priv_name = key_name
    pub_name = f"{priv_name}.pub"

    key = rsa.generate_private_key(
        backend=crypto_default_backend(), public_exponent=65537, key_size=4096
    )
    private_key = key.private_bytes(
        encoding=crypto_serialization.Encoding.PEM,
        format=crypto_serialization.PrivateFormat.PKCS8,
        encryption_algorithm=crypto_serialization.NoEncryption(),
    )
    public_key = key.public_key().public_bytes(
        encoding=crypto_serialization.Encoding.OpenSSH,
        format=crypto_serialization.PublicFormat.OpenSSH,
    )

    priv_path = local_dir / Path(priv_name)
    pub_path = local_dir / Path(pub_name)

    priv_path.write_bytes(private_key)
    pub_path.write_bytes(public_key)

    priv_path.chmod(0o600)

    with actions(roles=roles) as p:
        p.copy(src=str(priv_path), dest=f"/root/.ssh/{priv_name}", mode="600")
        p.copy(src=str(pub_path), dest=f"/root/.ssh/{pub_name}")
        p.lineinfile(
            path="/root/.ssh/authorized_keys",
            line=pub_path.read_text(),
            state="present",
        )

    return (priv_path, pub_path)


def run_play(
    play_source: Dict,
    *,
    inventory_path: Optional[str] = None,
    roles: Optional[RolesLike] = None,
    extra_vars: Optional[Mapping] = None,
    on_error_continue: bool = False,
) -> Results:
    """Run a play.

    Args:
        play_source (dict): ansible task
        inventory_path (str): inventory to use
        hosts: host like datastructure used as a drop in replacement for an inventory.
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
    # create a temporary file for holding the playbook beware that the file
    # might be re-opened during the context manager block and that lead to
    # unknown behavior on non-unix system In case of trouble, we might want to
    # have a homemade tempfile generation.
    #
    # This is super important to generate the file in the current directory avs
    # users often copy/sync file to remote machines using relative path on the
    # local machine. In Ansible, such path is relative to the playbook location.
    with NamedTemporaryFile(dir=Path.cwd()) as _tmp_file:
        play_path = Path(_tmp_file.name)
        logger.debug("Generating playbook in %s ", play_path)
        play_path.write_text(json.dumps([play_source]))
        return run_ansible(
            [str(play_path)],
            inventory_path=inventory_path,
            roles=roles,
            extra_vars=extra_vars,
            on_error_continue=on_error_continue,
        )


class _Phantom:
    """Internal stuff to build a chain of prefixes:

    a = actions()
    a.b.c.d() will call:
        action.__getattr__ and return p1 = Phantom(a, b, b)
        p1.__getattr__ and return p2 = Phantom(a, c, b.c)
        p2.__getattr__ and return p3 = Phantom(a, d, b.c.d)
        p3.__call__ and will add the built task to the parent action
    """

    def __init__(self, parent: "actions", current: str, prefix: str):
        self.parent = parent
        self.current = current
        self.prefix = prefix

    def __getattr__(self, name):
        return _Phantom(self.parent, name, f"{self.prefix}.{name}")

    def __call__(self, *args, **kwds):
        task_name = kwds.pop("task_name", self.prefix)
        task = {"name": task_name}
        # retrieve global kwargs
        _kwds = copy.copy(self.parent.kwds)
        # override with specific ones
        _kwds.update(kwds)
        # extract our specific kwargs
        background = _kwds.get("background", False)
        if not background:
            _kwds.pop("background", None)
        top_args, module_args = _split_args(**_kwds)
        task.update(top_args)

        if len(args) > 0:
            # free form (most likely shell, raw, command ...)
            task.update({self.prefix: args[0], "args": dict(**module_args)})
            self.parent.add_task(task)
        else:
            task.update({self.prefix: dict(**module_args)})
            self.parent.add_task(task)


class actions:
    """Context manager to run a set of remote actions on nodes


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
        background: A shortcut that injects async=1year, poll=0 to run the
            commands in detached mode. Can be overridden at the task level.
        strategy: ansible execution strategy
        kwargs: keyword arguments passed to :py:fun:`enoslib.api.run_ansible`.


    Examples:

        - Minimal snippet:

            .. code-block:: python

                with actions(roles=roles) as t:
                    t.apt(name=["curl", "git"], state="present")
                    t.shell("which docker || (curl get.docker.com | sh)")
                    t.docker_container(name="nginx", state="started")

        - Complete example with fact_gathering

            .. literalinclude:: examples/run_actions.py
                :language: python
                :linenos:

    .. hint::

        - Module can be run asynchronously using the corresponding Ansible options
            Note that not all the modules support asynchronous execution.

        - Note that the actual result isn't available in the result file but will
            be available through a file specified in the result object.

        - Any ansible module can be called using the above way. You'll need to
            refer to the module reference documentation to find the corresponding
            kwargs to use.
    """

    def __init__(
        self,
        *,
        pattern_hosts: str = "all",
        inventory_path: Optional[str] = None,
        roles: Optional[RolesLike] = None,
        gather_facts: bool = False,
        priors: Optional[List["actions"]] = None,
        run_as: Optional[str] = None,
        background: bool = False,
        strategy: str = "linear",
        **kwargs,
    ):

        self.pattern_hosts = pattern_hosts
        self.inventory_path = inventory_path
        self.roles = roles
        self.priors = priors if priors is not None else []
        self.strategy = strategy

        # run_ansible kwargs
        self.kwargs = kwargs

        # our specific global modules kwargs
        self.kwds = {}
        # Handle modification of task level kwargs
        if run_as is not None:
            self.kwds = dict(become=True, become_user=run_as)
        if background:
            # don't inject if background is False
            self.kwds = dict(background=True)
        # Will hold the tasks of the play corresponding to the sequence
        # of module call in this context/p
        self._tasks: List[Mapping[Any, Any]] = []

        if gather_facts:
            self._tasks.append(dict(name="Gather facts", setup=""))

        if self.priors:
            for prior in self.priors:
                self._tasks.extend(prior._tasks)

        # Placeholder (will be mutated) for the results
        self.results = Results()

    def add_task(self, task: Dict):
        self._tasks.append(task)

    def __getattr__(self, name: str):
        return _Phantom(self, name, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        play_source = dict(
            hosts=self.pattern_hosts,
            tasks=self._tasks,
            gather_facts=False,
            strategy=self.strategy,
        )

        logger.debug(play_source)

        # run it
        results = run_play(
            play_source,
            inventory_path=self.inventory_path,
            roles=self.roles,
            **self.kwargs,
        )

        # gather results (mutate the results attributes)
        for r in results:
            self.results.append(r)


class play_on(actions):
    def __init__(self, *args, **kwargs):
        warnings.warn("use actions instead of play_on", DeprecationWarning)
        super().__init__(*args, **kwargs)


# can be used as prior
__python3__ = actions()
__python3__.raw(
    (
        "(python --version | grep --regexp ' 3.*')"
        "||"
        "(apt update && apt install -y python3 python3-pip)"
    ),
    task_name="Install python3",
)
__default_python3__ = actions()
__default_python3__.raw(
    "update-alternatives --install /usr/bin/python python /usr/bin/python3 1",
    task_name="Making python3 the default python interpreter",
)


__docker__ = actions()
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
    with actions(priors=priors, gather_facts=False, **kwargs) as p:
        p.raw("hostname")


def run_command(
    command: str,
    *,
    pattern_hosts: str = "all",
    inventory_path: Optional[str] = None,
    roles: RolesLike = None,
    gather_facts: bool = False,
    extra_vars: Optional[Mapping] = None,
    on_error_continue: bool = False,
    run_as: Optional[str] = None,
    background: bool = False,
    task_name: str = None,
    raw: bool = False,
    **kwargs: Any,
) -> Results:
    """Run a shell command on some remote hosts.

    Args:
        command (str): the command to run
        pattern_hosts (str): pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html
        inventory_path (str): inventory to use
        roles (dict): the roles to use (replacement for inventory_path).
        extra_vars (dict): extra_vars to use
        gather_facts: True wheter facts should be gathered prior to the
            execution. Might be useful if Ansible variables are used.
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors
        run_as(str): run the command as this user.
            This is equivalent to passing become=yes and become_user=user but
            become_method can be passed to modify the privileged escalation
            method. (default to sudo).
        background: run the remote command in the background (detached mode)
            This is equivalent to passing async=one_year, poll=0
        task_name: name of the command to display, can be used for further
            filtering once the results is retrieved.
        raw: Whether to use a raw connection (no python requires at the destination)
        kwargs: keywords argument to pass to the shell module or as top level
            args.

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``

    Returns:
        Dict combining the stdout and stderr of ok and failed hosts and every
        result of tasks executed (this may include the fact gathering tasks)

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
    available through a file specified in the result object."""

    if run_as is not None:
        # run_as is a shortcut
        kwargs.update(become=True, become_user=run_as)

    if background:
        # don't inject if background is False
        kwargs.update(background=True)

    task = dict(name=command)
    if task_name is not None:
        task.update(name=task_name)
    if raw:
        task.update(raw=command)
    else:
        task.update(shell=command)

    top_args, module_args = _split_args(**kwargs)
    task.update(top_args)
    task.update(args=module_args)

    play_source = {
        "hosts": pattern_hosts,
        "gather_facts": gather_facts,
        "tasks": [task],
    }

    results = run_play(
        play_source,
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars,
        on_error_continue=on_error_continue,
    )

    return results


def run(cmd: str, roles: RolesLike, **kwargs) -> Results:
    """Run command on some hosts

    Args:
        cmd: the command to run.
            This accepts Ansible templates
        roles: host on which to run the command
        kwargs: keyword argument of `py:func:~enoslib.api.run_command`

    Returns:
        Dict combining the stdout and stderr of ok and failed hosts and every
        result of tasks executed (this may include the fact gathering tasks)

    """
    return run_command(cmd, roles=roles, **kwargs)


def gather_facts(
    *,
    pattern_hosts="all",
    gather_subset="all",
    inventory_path=None,
    roles: Optional[RolesLike] = None,
    extra_vars: Optional[Mapping] = None,
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
        result of tasks executed.

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
        s = {r.host: r.payload.get("ansible_facts") for r in _r}
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


def _dump_obj(obj):
    """Dump obj in a file.

    Args:
        obj: anything that is json serializable
    """
    try:
        dump_result = get_config()["dump_results"]
        if dump_result is not None:
            with dump_result.open("a") as f:
                json.dump(obj, f)

    except Exception as e:
        logger.error(
            "Error while saving results" "dump_result=%s, exception=%s", dump_result, e
        )


def run_ansible(
    playbooks: List[str],
    inventory_path: Optional[str] = None,
    roles: Optional[RolesLike] = None,
    tags: List[str] = None,
    on_error_continue: bool = False,
    basedir: Optional[str] = ".",
    extra_vars: Optional[Mapping] = None,
) -> Results:
    """Run Ansible.

    Args:
        playbooks (list): list of paths to the playbooks to run
        inventory_path (str): path to the hosts file (inventory)
        extra_vars (dict): extra vars to pass
        tags (list): list of tags to run
        on_error_continue(bool): Don't throw any exception in case a host is
            unreachable or the playbooks run with errors
        basedir: Ansible basedir
        ansible_retries: a generic retry mechanism. Set this to a positive
                         value if the connection plugin doesn't have this retry
                         mechanism (ssh does have one)

    Raises:
        :py:class:`enoslib.errors.EnosFailedHostsError`: if a task returns an
            error on a host and ``on_error_continue==False``
        :py:class:`enoslib.errors.EnosUnreachableHostsError`: if a host is
            unreachable (through ssh) and ``on_error_continue==False``
    """
    if not extra_vars:
        extra_vars = {}
    roles = _hostslike_to_roles(roles)
    inventory, variable_manager, loader = _load_defaults(
        inventory_path=inventory_path,
        roles=roles,
        extra_vars=extra_vars,
        tags=tags,
        basedir=basedir,
    )
    results: List[_AnsibleExecutionRecord] = []
    passwords: Dict = {}
    for path in playbooks:
        logger.debug(f"Running playbook {path} with vars:\n{extra_vars}")
        _results: List[_AnsibleExecutionRecord] = []
        callback = _MyCallback(_results)
        pbex = PlaybookExecutor(
            playbooks=[path],
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            passwords=passwords,
        )
        # hack ahead
        pbex._tqm._callback_plugins.append(callback)

        if get_config()["ansible_stdout"] == "noop":
            pbex._tqm._stdout_callback = NoopCallback()
        elif get_config()["ansible_stdout"] == "spinner":
            pbex._tqm._stdout_callback = SpinnerCallback()
        else:
            # let the ansible.cfg governs this
            pass
        _ = pbex.run()

        results += _results

        # Handling errors
        failed_hosts = []
        unreachable_hosts = []
        for r in _results:
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

    final_results: Results = Results.from_ansible(results)
    # dump if needed
    _dump_obj(final_results.to_dict(include_payload=True))
    return final_results


def _sync_from_facts(roles: Roles, networks: Networks, facts: Dict) -> Roles:
    """Add the network information to the host in roles.

    Do it in place.
    """
    for hosts in roles.values():
        for host in hosts:
            # only sync if host is really a Host (not a Sensor for example)
            if not isinstance(host, Host):
                continue
            host_facts = facts[host.alias]
            host.sync_from_ansible(networks, host_facts)
    return roles


def sync_info(
    roles: RolesLike, networks: Networks, inplace=False, **kwargs
) -> RolesLike:
    """Sync each host network information with their actual configuration

    If the command is successful some host attributes will be
    populated. This allows to resync the enoslib Host representation with the
    remote configuration.

    This method is generic: should work for any provider and supports IPv4
    and IPv6 addresses.

    Args:
        roles (dict): role->hosts mapping as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        networks (list): network list as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        inplace: bool, default False
            If False, return a copy of roles. Otherwise, do operation inplace.
        kwargs: keyword arguments passed to :py:fun:`enoslib.api.run_ansible`

    Returns:
        RolesLike of the same type as passed. With updated information.

    """
    if not roles:
        logger.warning("The Roles are empty at this point !")
        return roles
    wait_for(roles, **kwargs)

    with TemporaryDirectory() as tmp_dir:
        facts_file = Path(tmp_dir) / "facts"
        logger.debug("Syncing host description in %s", facts_file)
        utils_playbook = os.path.join(ANSIBLE_DIR, "utils.yml")
        options = {
            "enos_action": "check_network",
            "facts_file": str(facts_file),
        }
        run_ansible(
            [utils_playbook],
            roles=roles,
            extra_vars=options,
            on_error_continue=False,
            **kwargs,
        )

        # Read the file
        # Match provider networks to interface names for each host
        # preserve the host from being mutated wildly
        with facts_file.open("r") as f:
            facts = json.load(f)
            _roles: Optional[Roles] = _hostslike_to_roles(roles)
            if _roles is None:
                raise ValueError("Roles is None")
            if not inplace:
                _roles_copied: Roles = copy.deepcopy(_roles)
            else:
                _roles_copied = _roles
            _roles_copied = _sync_from_facts(_roles_copied, networks, facts)
            # return the right type
            if isinstance(roles, Roles):
                return _roles_copied
            if isinstance(roles, Host):
                return _roles_copied["all"][0]
            if hasattr(roles, "__iter__"):
                return _roles_copied["all"]
    raise ValueError("The impossible happened ! The roles aren't Roles")


def generate_inventory(
    roles: Roles,
    networks: Networks,
    inventory_path: str,
    check_networks=False,
):
    """Generate an inventory file in the ini format.

    The inventory is generated using the ``roles`` in the ``ini`` format.  If
    ``check_network == True``, the function will try to discover which networks
    interfaces are available and map them to one network of the ``networks``
    parameters.  Note that this auto-discovery feature requires the servers to
    have their IP set.

    Args:
        roles         : role->hosts mapping as returned by
                        :py:meth:`enoslib.infra.provider.Provider.init`
        networks      : role->networks mapping as returned by
                        :py:meth:`enoslib.infra.provider.Provider.init`
        inventory_path: path to the inventory to generate
        check_networks: True to sync the hosts before dumping the inventory.
    """
    with open(inventory_path, "w") as f:
        f.write(_generate_inventory(roles))

    if check_networks:
        _roles = sync_info(roles, networks)
        with open(inventory_path, "w") as f:
            f.write(_generate_inventory(_roles))


def get_hosts(roles: Roles, pattern_hosts: str = "all") -> Sequence[Host]:
    """Get all the hosts matching the pattern.

    Args:
        roles: the roles as returned by
            :py:meth:`enoslib.infra.provider.Provider.init`
        pattern_hosts: pattern to describe ansible hosts to target.
            see https://docs.ansible.com/ansible/latest/intro_patterns.html

    Return:
        The list of hosts matching the pattern
    """
    all_hosts: Set[Host] = set()
    for hosts in roles.values():
        all_hosts = all_hosts.union(set(hosts))
    inventory = EnosInventory(roles=roles)
    ansible_hosts = inventory.get_hosts(pattern=pattern_hosts)
    ansible_addresses = [h.address for h in ansible_hosts]
    return [h for h in all_hosts if h.address in ansible_addresses]


def wait_for(
    roles: RolesLike, retries: int = 100, interval: int = 30, **kwargs
) -> None:
    """Wait for all the machines to be ready to run some commands.

    Let Ansible initiates a communication and retries if needed.
    Communication backend depends on the connection plugin used. This is most
    likely SSH but alternative backend can be used
    (see `connection plugins
    <https://docs.ansible.com/ansible/latest/plugins/connection.html>`_)

    Args:
        roles: Roles to wait for
        retries: Number of time we'll be retrying a connection
        interval: Interval to wait in seconds between two retries
        kwargs: keyword arguments passed to :py:fun:`enoslib.api.run_ansible`
    """
    for i in range(0, retries):
        try:
            with actions(
                roles=roles, gather_facts=False, on_error_continue=False, **kwargs
            ) as p:
                # We use the raw module because we can't assume at this point that
                # python is installed
                p.raw("hostname", task_name="Waiting for connection")
            break
        except EnosUnreachableHostsError:
            logger.info(f"Retrying... {i + 1}/{retries}")
            time.sleep(interval)
    else:
        raise EnosSSHNotReady("Maximum retries reached")


def bg_start(key: str, cmd: str) -> str:
    """Put a command in the background.

    Generate the command that will put cmd in background.
    This uses tmux to detach cmd from the current shell session.

    Idempotent

    Args:
        key: session identifier for tmux (must be unique)
        cmd: the command to put in background

    Returns:
        command encapsulated in a tmux session identified by the key

    """
    # supports templating
    return f"(tmux ls | grep {key}) ||tmux new-session -s {key} -d '{cmd}'"


def bg_stop(key: str, num: int = signal.SIGINT) -> str:
    """Stop a command that runs in the background.

    Generate the command that will stop a previously started command in the
    background with :py:func:`~enoslib.api.background_start`

    Args:
        key: session identifier for tmux.

    Returns:
        command that will stop a tmux session
    """
    if num == signal.SIGHUP:
        # default tmux termination signal
        # This will send SIGHUP to all the encapsulated processes
        return f"tmux kill-session -t {key} || true"
    else:
        # We prefer send a sigint to all the encapsulated processes
        cmd = (
            "(tmux list-panes -t %s -F '#{pane_pid}' | " "xargs -n1 kill -%s) || true"
        ) % (key, int(num))
        return cmd


# Private zone
def _generate_inventory(roles):
    """Generates an inventory files from roles

    roles: dict of roles (roles -> list of Host)
    """
    inventory = EnosInventory(roles=roles)
    return inventory.to_ini_string()
