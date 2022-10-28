import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type=[])
    .add_machine(
        roles=["city", "paris"],
        cluster="paravance",
        nodes=1,
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="paravance",
        nodes=1,
    )
    .add_machine(
        roles=["city", "londres"],
        cluster="paravance",
        nodes=1,
    )
)
provider = en.G5k(conf)
roles, networks = provider.init()

sources = []
for idx, host in enumerate(roles["city"]):
    delay = 5 * idx
    print(f"{host.alias} <-> {delay}")
    inbound = en.NetemOutConstraint(device="br0", options=f"delay {delay}ms")
    outbound = en.NetemInConstraint(device="br0", options=f"delay {delay}ms")
    sources.append(en.NetemInOutSource(host, constraints={inbound, outbound}))

en.netem(sources)
