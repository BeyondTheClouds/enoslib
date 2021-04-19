import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

CLUSTER = "paravance"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

prod = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
private = en.G5kNetworkConf(id="n2", type="kavlan", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(job_name=__file__)
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


netem = en.NetemHTB()
(
    netem.add_constraints(
        src=roles["paris"],
        dest=roles["londres"],
        delay="10ms",
        rate="1gbit",
        symetric=True,
        networks=networks["private"],
    )
    .add_constraints(
        src=roles["paris"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symetric=True,
        networks=networks["private"],
    )
    .add_constraints(
        src=roles["londres"],
        dest=roles["berlin"],
        delay="20ms",
        rate="1gbit",
        symetric=True,
        networks=networks["private"],
    )
)
netem.deploy()
netem.validate()
# netem.destroy()
