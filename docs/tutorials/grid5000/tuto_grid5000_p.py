from pathlib import Path

import enoslib as en


_ = en.init_logging()


job_name = Path(__file__).name

# claim the resources
network = en.G5kNetworkConf(type="kavlan", roles=["my_network"], site="rennes")
conf = (
    en.G5kConf.from_settings(job_name=job_name)
    .add_network_conf(network)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=network
    )
    .add_machine(
        roles=["control", "compute"],
        cluster="paravance",
        nodes=1,
        primary_network=network,
    )
    .finalize()
)

provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()
