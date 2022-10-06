from pathlib import Path

import enoslib as en

logging = en.init_logging()

CLUSTER = "paravance"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

prod = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
private = en.G5kNetworkConf(id="n2", type="kavlan", roles=["private"], site=SITE)

conf = (
    en.G5kConf.from_settings(
        job_name=job_name, job_type=["deploy"], env_name="debian11-nfs"
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

# Building the network constraints
emulation_conf = {
    "default_delay": "20ms",
    "default_rate": "1gbit",
    "except": [],
    "default_network": "private",
    "constraints": [
        {"src": "paris", "dst": "londres", "symetric": True, "delay": "10ms"}
    ],
}

logging.info(emulation_conf)

netem = en.NetemHTB.from_dict(emulation_conf, roles, networks)
netem.destroy()
netem.deploy()
netem.validate()
