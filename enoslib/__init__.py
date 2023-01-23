# flake8: noqa
import logging
from typing import Any, Dict, List, Optional, Tuple

from enoslib.api import (
    DEFAULT_ERROR_STATUSES,
    STATUS_FAILED,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_UNREACHABLE,
    actions,
    ensure_python3,
    gather_facts,
    generate_inventory,
    get_hosts,
    play_on,
    run,
    run_ansible,
    run_command,
    run_play,
    sync_info,
    wait_for,
)
from enoslib.config import config_context, set_config
from enoslib.docker import DockerHost, get_dockers

# Multi providers
from enoslib.infra.providers import Providers
from enoslib.local import LocalHost
from enoslib.objects import DefaultNetwork, Host, Network, Networks, Roles

# Services
from enoslib.service.conda.conda import Dask, conda_from_env, in_conda_cmd
from enoslib.service.docker.docker import Docker
from enoslib.service.dstat.dstat import Dstat
from enoslib.service.emul.htb import (
    AccurateNetemHTB,
    HTBConstraint,
    HTBSource,
    NetemHTB,
    netem_htb,
)
from enoslib.service.emul.netem import (
    Netem,
    NetemInConstraint,
    NetemInOutSource,
    NetemOutConstraint,
    netem,
)
from enoslib.service.k3s.k3s import K3s
from enoslib.service.locust.locust import Locust
from enoslib.service.monitoring.monitoring import TIGMonitoring, TPGMonitoring
from enoslib.service.skydive.skydive import Skydive
from enoslib.service.tcpdump import TCPDump

# Providers
try:
    from enoslib.infra.enos_g5k import g5k_api_utils
    from enoslib.infra.enos_g5k.configuration import (
        ClusterConfiguration as G5kClusterConf,
    )
    from enoslib.infra.enos_g5k.configuration import Configuration as G5kConf
    from enoslib.infra.enos_g5k.configuration import (
        NetworkConfiguration as G5kNetworkConf,
    )
    from enoslib.infra.enos_g5k.configuration import (
        ServersConfiguration as G5kServersConf,
    )
    from enoslib.infra.enos_g5k.provider import G5k, G5kTunnel
except ImportError:
    pass

try:
    from enoslib.infra.enos_vagrant.configuration import Configuration as VagrantConf
    from enoslib.infra.enos_vagrant.configuration import (
        MachineConfiguration as VagrantMachineMachineConf,
    )
    from enoslib.infra.enos_vagrant.configuration import (
        NetworkConfiguration as VagrantNetworkConf,
    )
    from enoslib.infra.enos_vagrant.provider import Enos_vagrant as Vagrant
except ImportError:
    pass

try:
    from enoslib.infra.enos_distem.configuration import Configuration as DistemConf
    from enoslib.infra.enos_distem.configuration import (
        MachineConfiguration as DistemMachineConf,
    )
    from enoslib.infra.enos_distem.provider import Distem
except ImportError:
    pass


from enoslib.infra.enos_static.configuration import Configuration as StaticConf
from enoslib.infra.enos_static.configuration import (
    MachineConfiguration as StaticMachineConf,
)
from enoslib.infra.enos_static.configuration import (
    NetworkConfiguration as StaticNetworkConf,
)
from enoslib.infra.enos_static.provider import Static

try:
    from enoslib.infra.enos_vmong5k.configuration import Configuration as VMonG5kConf
    from enoslib.infra.enos_vmong5k.configuration import (
        MachineConfiguration as VMonG5KMachineConf,
    )
    from enoslib.infra.enos_vmong5k.provider import (
        VMonG5k,
        mac_range,
        start_virtualmachines,
    )
except ImportError:
    pass


try:
    from enoslib.infra.enos_iotlab.configuration import Configuration as IotlabConf
    from enoslib.infra.enos_iotlab.objects import (
        IotlabSensor,
        IotlabSerial,
        IotlabSniffer,
    )
    from enoslib.infra.enos_iotlab.provider import Iotlab
except ImportError:
    pass

try:

    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        Configuration as CBMConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        Configuration as CKVMConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        MachineConfiguration as CBMMachineConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        MachineConfiguration as CKVMMachineConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.provider import Chameleonbaremetal as CBM
    from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm as CKVM
    from enoslib.infra.enos_openstack.configuration import Configuration as OSConf
    from enoslib.infra.enos_openstack.configuration import (
        MachineConfiguration as OSMachineConf,
    )
    from enoslib.infra.enos_openstack.provider import Openstack as OS
except ImportError as e:
    pass

try:
    from enoslib.infra.enos_chameleonedge.configuration import (
        Configuration as ChameleonEdgeConf,
    )
    from enoslib.infra.enos_chameleonedge.provider import ChameleonEdge
except ImportError:
    pass


# Tasks
from enoslib.task import Environment, enostask

# Some util functions
from .version import __chat__, __documentation__, __source__, __version__

MOTD = f"""
  _____        ___  ____  _ _ _
 | ____|_ __  / _ \\/ ___|| (_) |__
 |  _| | '_ \\| | | \\___ \\| | | '_ \\
 | |___| | | | |_| |___) | | | |_) |
 |_____|_| |_|\\___/|____/|_|_|_.__/  {__version__}

"""
INFO = f"""
- Documentation: [{__documentation__}]({__documentation__})
- Source: [{__source__}]({__source__})
- Chat: [{__chat__}]({__chat__})
"""


def _check_deps() -> List[Tuple[str, Optional[bool], str, str]]:
    import importlib

    prefix = "enoslib.infra"
    providers = [
        ("Chameleon", "enos_chameleonbaremetal", r"pip install enoslib\[chameleon]"),
        ("ChameleonKVM", "enos_chameleonkvm", r"pip install enoslib\[chameleon]"),
        ("ChameleonEdge", "enos_chameleonedge", r"pip install enoslib\[chameleon]"),
        ("Distem", "enos_distem", r"pip install enoslib\[distem]"),
        ("IOT-lab", "enos_iotlab", r"pip install enoslib\[iotlab]"),
        ("Grid'5000", "enos_g5k", ""),
        ("Openstack", "enos_openstack", r"pip install enoslib\[chameleon]"),
        ("Vagrant", "enos_vagrant", r"pip install enoslib\[vagrant]"),
        ("VMonG5k", "enos_vmong5k", ""),
    ]
    deps: List[Tuple[str, Optional[bool], str, str]] = []
    for shortname, provider, hint in providers:
        mod = f"{prefix}.{provider}.provider"
        try:
            importlib.import_module(mod)
            deps.append((shortname, True, "", mod))
        except ImportError:
            deps.append((shortname, False, hint, mod))
    return deps


def _print_deps_table(deps: List[Tuple[str, Optional[bool], str, str]], console):
    from rich.table import Table

    table = Table(title="Dependency check")
    table.add_column("Provider")
    table.add_column("Status", justify="center")
    table.add_column("Hint", no_wrap=True, width=30)
    for (shortname, deps_ok, hint, _) in deps:
        table.add_row(
            shortname,
            "[green]INSTALLED[/green]" if deps_ok else "[blue]NOT INSTALLED[/blue]",
            hint,
        )

    console.print(table)


def _print_conn_table(deps: List[Tuple[str, Optional[bool], str, str]], console):
    import importlib

    from rich.table import Table

    filtered: List[Tuple[str, str]] = [
        (shortname, mod) for (shortname, deps_ok, _, mod) in deps if deps_ok
    ]
    statuses: List[Tuple[str, str, Optional[bool], str]] = []
    for shortname, mod in filtered:
        m = importlib.import_module(mod)
        check_fnc = getattr(m, "check", None)
        if check_fnc is not None:
            # inject shortname again
            try:
                returned_status: List[Tuple[str, bool, str]] = check_fnc()
                for status in returned_status:
                    current_status: Tuple[str, str, bool, str] = (
                        shortname,
                        status[0],
                        status[1],
                        status[2],
                    )
                    statuses.append(current_status)
            except Exception as e:
                statuses.append((shortname, "❔", False, str(e)))
        else:
            statuses.append((shortname, "❔", None, "no info available"))

    table = Table(title="Connectivity check")
    table.add_column("Provider")
    table.add_column("Key")
    table.add_column("Connectivity", justify="center")
    table.add_column("Hint", no_wrap=True, width=30)

    for (shortname, key, status_ok, hint) in statuses:
        if status_ok is None:
            status_str = "❔"
        elif status_ok:
            status_str = "✅"
        else:
            status_str = "❌"
        table.add_row(shortname, key, status_str, hint)

    console.print(table)


def check():
    """Check the status of EnOSlib.

    This gives you a synthetic view of

    - the installed providers (dependency check)
    - the connectivity to the various providers (connectivity check)

    The dependency check test which optional dependencies are installed with
    your EnOSlib version.
    The connectivity check if connection to the various providers'
    infrastructure can be initiated. Since each provider setup is specific, this
    gives you a quick feedback on your local configuration.
    """
    _ = init_logging()
    deps = _check_deps()

    from rich.console import Console
    from rich.markdown import Markdown
    from rich.text import Text

    console = Console()

    text = Text(MOTD, justify="left")
    console.print(text)
    console.print(Markdown(INFO))
    _print_deps_table(deps, console)

    with config_context(ansible_stdout="noop"):
        _print_conn_table(deps, console)


def init_logging(level=logging.INFO, **kwargs):
    """Enable Rich display of log messages.

    kwargs: kwargs passed to RichHandler.
      EnOSlib chooses some defaults for you
        show_time=False,
    """
    from rich.logging import RichHandler

    default_kwargs: Dict[str, Any] = dict(
        show_time=False,
    )

    default_kwargs.update(**kwargs)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(**default_kwargs)],
    )

    # enable Rich outputs
    set_config(ansible_stdout="spinner")

    return logging
