import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

CLUSTER = "parasilo"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

private = en.G5kNetworkConf(type="kavlan", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(
        job_name=job_name, job_type=["deploy"], env_name="debian11-nfs"
    )
    .add_network_conf(private)
    .add_machine(
        roles=["paris"],
        cluster=CLUSTER,
        nodes=1,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["londres"],
        cluster=CLUSTER,
        nodes=1,
        secondary_networks=[private],
    )
    .add_machine(
        roles=["berlin"],
        cluster=CLUSTER,
        nodes=1,
        secondary_networks=[private],
    )
)

provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)


netem = en.NetemHTB()
(
    netem.add_constraints(
        src=roles["paris"],
        dest=roles["londres"],
        delay="10ms",
        rate="1gbit",
        symmetric=True,
        networks=networks["private"],
    )
    .add_constraints(
        src=roles["paris"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symmetric=True,
        networks=networks["private"],
    )
    .add_constraints(
        src=roles["londres"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symmetric=True,
        networks=networks["private"],
    )
)
netem.deploy()
netem.validate()
# netem.destroy()
