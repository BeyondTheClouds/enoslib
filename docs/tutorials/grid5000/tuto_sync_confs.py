from enoslib.infra.enos_g5k.provider import synchronise
from pathlib import Path

import enoslib as en

en.init_logging()

job_name = Path(__file__).name

# claim the resources
network1 = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site="lyon")

conf1 = (
    en.G5kConf.from_settings(
        job_type=["allow_classic_ssh", "exotic"], job_name=f"{job_name}-1"
    )
    .add_network_conf(network1)
    .add_machine(roles=["control"], cluster="pyxis", nodes=1, primary_network=network1)
    .finalize()
)

network2 = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site="rennes")

conf2 = (
    en.G5kConf.from_settings(job_type=["allow_classic_ssh"], job_name=f"{job_name}-2")
    .add_network_conf(network2)
    .add_machine(
        roles=["control"], cluster="paravance", nodes=1, primary_network=network2
    )
    .finalize()
)

start = synchronise(conf1, conf2)
conf1.reservation = start
conf2.reservation = start
g5k1 = en.G5k(conf1)
g5k1.reserve_async()
g5k2 = en.G5k(conf2)
roles2, networks2 = g5k2.init()
roles1, networks1 = g5k1.init()
