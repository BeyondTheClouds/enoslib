import logging
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

conf = (
    en.VMonG5kConf()
    .from_settings(job_name=job_name)
    .add_machine(roles=["server"], cluster="ecotype", number=1)
    .add_machine(roles=["client"], cluster="ecotype", number=1)
)

provider = en.VMonG5k(conf)

roles, networks = provider.init()
en.wait_for(roles)

with en.actions(roles=roles) as p:
    p.apt(
        name=["flent", "netperf", "python3-setuptools", "python3-matplotlib"],
        state="present",
    )

with en.actions(pattern_hosts="server", roles=roles) as p:
    p.shell("nohup netperf &")

with en.actions(pattern_hosts="client", roles=roles) as p:
    server_address = roles["server"][0].address
    p.shell(
        "flent rrul -p all_scaled "
        + "-l 60 "
        + f"-H { server_address } "
        + "-t 'bufferbloat test' "
        + "-o result.png"
    )
    p.fetch(src="result.png", dest="result")
