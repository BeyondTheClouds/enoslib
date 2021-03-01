# flake8: noqa
from enoslib.api import (
    ensure_python2,
    ensure_python3,
    sync_info,
    get_hosts,
    play_on,
    run,
    run_ansible,
    run_command,
    run_play,
    wait_for,
)

from enoslib.objects import Host, Network, Roles, Networks
from enoslib.docker import DockerHost, get_dockers

# Services
from enoslib.service.conda.conda import Dask, in_conda_cmd

from enoslib.service.docker.docker import Docker
from enoslib.service.dstat.dstat import Dstat
from enoslib.service.locust.locust import Locust
from enoslib.service.k3s.k3s import K3s
from enoslib.service.monitoring.monitoring import TIGMonitoring, TPGMonitoring
from enoslib.service.emul.netem import Netem, netem, NetemOutConstraint, NetemInOutSource, NetemInConstraint
from enoslib.service.emul.htb import netem_htb, NetemHTB, HTBConstraint, HTBSource

from enoslib.service.skydive.skydive import Skydive

# Providers
from enoslib.infra.enos_g5k.provider import G5k, G5kTunnel
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from enoslib.infra.enos_g5k.configuration import Configuration as G5kConf
from enoslib.infra.enos_g5k.configuration import NetworkConfiguration as G5kNetworkConf
from enoslib.infra.enos_g5k.configuration import ServersConfiguration as G5kServersConf
from enoslib.infra.enos_g5k.configuration import ClusterConfiguration as G5kClusterConf

from enoslib.infra.enos_vagrant.provider import Enos_vagrant as Vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration as VagrantConf
from enoslib.infra.enos_vagrant.configuration import (
    MachineConfiguration as VagrantMachineMachineConf,
)
from enoslib.infra.enos_vagrant.configuration import (
    NetworkConfiguration as VagrantNetworkConf,
)

from enoslib.infra.enos_distem.provider import Distem
from enoslib.infra.enos_distem.configuration import Configuration as DistemConf
from enoslib.infra.enos_distem.configuration import (
    MachineConfiguration as DistemMachineConf,
)


from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration as StaticConf
from enoslib.infra.enos_static.configuration import (
    MachineConfiguration as StaticMachineConf,
)
from enoslib.infra.enos_static.configuration import (
    NetworkConfiguration as StaticNetworkConf,
)

from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration as VMonG5kConf
from enoslib.infra.enos_vmong5k.configuration import (
    MachineConfiguration as VMonG5KMachineConf,
)
from enoslib.infra.enos_vmong5k.provider import start_virtualmachines

from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.infra.enos_iotlab.configuration import Configuration as IotlabConf
from enoslib.infra.enos_iotlab.objects import IotlabSensor, IotlabSniffer, IotlabSerial

try:

    from enoslib.infra.enos_chameleonbaremetal.provider import Chameleonbaremetal as CBM
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        Configuration as CBMConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        MachineConfiguration as CBMMachineConf,
    )

    from enoslib.infra.enos_chameleonkvm.provider import Chameleonkvm as CKVM
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        Configuration as CKVMConf,
    )
    from enoslib.infra.enos_chameleonbaremetal.configuration import (
        MachineConfiguration as CKVMMachineConf,
    )

    from enoslib.infra.enos_openstack.provider import Openstack as OS
    from enoslib.infra.enos_openstack.configuration import (
        MachineConfiguration as OSMachineConf,
    )

except ModuleNotFoundError:
    print("Note: Openstack clients not installed")

# Tasks
from enoslib.task import enostask, Environment
