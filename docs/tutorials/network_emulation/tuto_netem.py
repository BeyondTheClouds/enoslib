import logging
from pathlib import Path

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

prod_network = G5kNetworkConf(
    id="n1",
    type="prod",
    roles=["my_network"],
    site="rennes"
)
conf = (
    G5kConf.from_settings(job_name=job_name, job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_machine(
        roles=["city", "paris"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["city", "londres"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
)
provider = G5k(conf)
roles, networks = provider.init()

sources = []
for idx, host in enumerate(roles["city"]):
    delay = 5 * idx
    print(f"{host.alias} <-> {delay}")
    inbound = NetemOutConstraint(device="br0", options=f"delay {delay}ms")
    outbound = NetemInConstraint(device="br0", options=f"delay {delay}ms")
    sources.append(NetemInOutSource(host, inbounds=[inbound], outbounds=[outbound]))

netem(sources)