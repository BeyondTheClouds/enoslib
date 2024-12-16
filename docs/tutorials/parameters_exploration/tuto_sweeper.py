import logging
import os
import traceback
from pathlib import Path
from typing import Dict

from execo_engine import ParamSweeper, sweep

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

CLUSTER = "paradoxe"

# Set high parallelism to be able to handle a large number of VMs
# efficiently.
en.set_config(ansible_forks=64)

# Enable Ansible pipelining for better performance
os.environ["ANSIBLE_PIPELINING"] = "True"


def bench(parameter: Dict) -> None:
    """Launch a benchmark.

    1. Start the required resources.
    2. Prepare the virtual machines
    3. Benchmark the network
    4. Backup
    """
    nb_vms = parameter["nb_vms"]
    conf = (
        en.VMonG5kConf.from_settings(force_deploy=True)
        .add_machine(roles=["server"], cluster=CLUSTER, number=nb_vms, flavour="tiny")
        .add_machine(roles=["client"], cluster=CLUSTER, number=nb_vms, flavour="tiny")
    )

    provider = en.VMonG5k(conf)

    roles, networks = provider.init()
    roles = en.sync_info(roles, networks)

    servers = roles["server"]
    clients = roles["client"]

    for s, c in zip(servers, clients):
        c.extra.update(target=s.address)

    with en.actions(roles=roles) as p:
        p.apt(
            name=[
                "flent",
                "netperf",
                "python3-setuptools",
                "python3-matplotlib",
                "tmux",
            ],
            state="present",
        )

    with en.actions(pattern_hosts="server", roles=roles) as p:
        p.shell("tmux new-session -d 'exec netperf'")

    delay = parameter["delay"]
    if delay is not None:
        netem = en.Netem()
        (
            netem.add_constraints(
                f"delay {delay}", roles["client"], symmetric=False
            ).add_constraints(f"delay {delay}", roles["server"], symmetric=False)
        )
        netem.deploy()
    output = f"tcp_upload_{nb_vms}_{delay}"
    with en.actions(pattern_hosts="client", roles=roles) as p:
        p.shell(
            "flent tcp_upload -p totals "
            + "-l 60 "
            + "-H {{ target }} "
            + f"-t '{output}' "
            + f"-o {output}.png",
            task_name=f"Benchmarkings with {output}",
        )
        p.fetch(src=f"{output}.png", dest=f"result_{output}")


parameters = dict(nb_vms=[1, 2, 4, 8, 16], delay=[None, "0ms", "10ms", "50ms"])


sweeps = sweep(parameters)
sweeper = ParamSweeper(
    persistence_dir=str(Path("sweeps")), sweeps=sweeps, save_sweeps=True
)

parameter = sweeper.get_next()
while parameter:
    try:
        print(parameter)
        bench(parameter)
        sweeper.done(parameter)
    except Exception:
        traceback.print_exc()
        sweeper.skip(parameter)
    finally:
        parameter = sweeper.get_next()
