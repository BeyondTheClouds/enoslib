import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

GARAGE_URL = (
    "https://garagehq.deuxfleurs.fr/_releases/v0.7.3/"
    "x86_64-unknown-linux-musl/garage"
)
job_name = Path(__file__).name

conf = (
    en.G5kConf()
    .from_settings(job_name=job_name, walltime="0:40:00")
    .add_machine(roles=["garage"], cluster="ecotype", nodes=2)
)

provider = en.G5k(conf)

roles, networks = provider.init()

with en.actions(roles=roles["garage"], gather_facts=True) as p:
    p.get_url(
        task_name="Download garage",
        url=GARAGE_URL,
        dest="/tmp/garage",
        mode="755",
    )
    p.template(
        task_name="Create config",
        src=str(Path(__file__).parent / "garage.toml.j2"),
        dest="/tmp/garage.toml",
    )
    p.command(
        task_name="Kill garage if already running",
        cmd="killall garage",
        ignore_errors=True,
    )
    p.command(
        task_name="Run garage in the background",
        cmd="/tmp/garage -c /tmp/garage.toml server",
        background=True,
    )
    p.command(
        task_name="Get node ID",
        cmd="/tmp/garage -c /tmp/garage.toml node id -q",
    )

# Collect Garage nodes ID in a dictionary
results = p.results
nodes_id = {r.host: r.stdout for r in results.filter(task="Get node ID")}

with en.actions(roles=roles["garage"], gather_facts=False) as p:
    for remote_node, remote_id in nodes_id.items():
        p.command(
            task_name=f"Connect to remote node {remote_node}",
            cmd=f"/tmp/garage -c /tmp/garage.toml node connect {remote_id}",
        )


# Release all Grid'5000 resources
provider.destroy()
