from pathlib import Path

import enoslib as en

en.init_logging()

job_name = Path(__file__).name

prod_network = en.G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_network_conf(prod_network)
    .add_machine(
        roles=["city", "paris"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network,
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network,
    )
    .add_machine(
        roles=["city", "londres"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network,
    )
    .finalize()
)
provider = en.G5k(conf)
roles, networks = provider.init()

sources = []
for idx, host in enumerate(roles["city"]):
    delay = 5 * idx
    print(f"{host.alias} <-> {delay}")
    inbound = en.NetemOutConstraint(device="br0", options=f"delay {delay}ms")
    outbound = en.NetemInConstraint(device="br0", options=f"delay {delay}ms")
    sources.append(en.NetemInOutSource(host, constraints=[inbound, outbound]))

en.netem(sources)
