import traceback
from pathlib import Path
from typing import Dict

from execo_engine import ParamSweeper, sweep

import enoslib as en

en.init_logging()

CLUSTER = "paranoia"


def bench(parameter: Dict) -> None:
    """Launch a benchmark.

    1. Start the required ressources.
    2. Prepare the virtual machines
    3. Benchmark the network
    4. Backup
    """
    nb_vms = parameter["nb_vms"]
    conf = (
        en.VMonG5kConf.from_settings(force_deploy=True)
        .add_machine(roles=["server"], cluster=CLUSTER, number=nb_vms, flavour="tiny")
        .add_machine(roles=["client"], cluster=CLUSTER, number=nb_vms, flavour="tiny")
        .finalize()
    )

    provider = en.VMonG5k(conf)

    roles, networks = provider.init()
    roles = en.sync_info(roles, networks)

    servers = roles["server"]
    clients = roles["client"]

    for s, c in zip(servers, clients):
        c.extra.update(target=s.address)

    with en.actions(roles=roles) as p:
        p.apt_repository(
            repo="deb http://deb.debian.org/debian stretch main contrib non-free",
            state="present",
        )
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

    with en.action(pattern_hosts="server", roles=roles) as p:
        p.shell("tmux new-session -d 'exec netperf'")

    delay = parameter["delay"]
    if delay is not None:
        tc = dict(default_delay=delay, default_rate="10gbit", enabled=True)
        netem = en.Netem(tc, roles=roles)
        netem.deploy()
    output = f"tcp_upload_{nb_vms}_{delay}"
    with en.actions(pattern_hosts="client", roles=roles) as p:
        p.shell(
            "flent tcp_upload -p totals "
            + "-l 60 "
            + "-H {{ target }} "
            + f"-t '{output}' "
            + f"-o {output}.png",
            display_name=f"Benchmarkings with {output}",
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
