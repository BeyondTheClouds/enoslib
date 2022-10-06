import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

CLUSTER = "paravance"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

prod = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
private = en.G5kNetworkConf(id="n2", type="kavlan-global", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        walltime="00:30:00",
        job_type=["deploy"],
        env_name="debian11-nfs",
    )
    .add_network_conf(prod)
    .add_network_conf(private)
    .add_machine(
        roles=["paris"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["londres"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["berlin"],
        cluster=CLUSTER,
        nodes=1,
        primary_network=prod,
        secondary_networks=[private],
    )
    .finalize()
)

provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)

netem = en.Netem()
(
    netem.add_constraints(
        "delay 10ms", roles["paris"], networks=networks["private"], symmetric=True
    )
    .add_constraints(
        "delay 20ms", roles["londres"], networks=networks["private"], symmetric=True
    )
    .add_constraints(
        "delay 30ms", roles["berlin"], networks=networks["private"], symmetric=True
    )
)

netem.deploy()
netem.validate()

for role, hosts in roles.items():
    print(role)
    for host in hosts:
        print(f"-- {host.alias}")
