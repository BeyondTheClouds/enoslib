from enoslib import *
from pathlib import Path

import logging


logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

prod_network = G5kNetworkConf(id="id", roles=["mynetwork"], type="prod", site="rennes")
conf = (
    G5kConf
    .from_settings(job_name=job_name,
                   job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_machine(
        roles=["server"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["client"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
)

provider = G5k(conf)
roles, networks = provider.init()
roles = sync_network_info(roles, networks)
with play_on(roles=roles) as p:
    # flent requires python3, so we default python to python3
    p.shell("update-alternatives --install /usr/bin/python python /usr/bin/python3 1")
    p.apt_repository(repo="deb http://deb.debian.org/debian stretch main contrib non-free",
                     state="present")
    p.apt(name=["flent", "netperf", "python3-setuptools", "python3-matplotlib"],
          state="present")

with play_on(pattern_hosts="server", roles=roles) as p:
    p.shell("nohup netperf &")

with play_on(pattern_hosts="client", roles=roles) as p:
    server_address = roles["server"][0].address
    p.shell("flent rrul -p all_scaled "
            + "-l 60 "
            + f"-H { server_address } "
            + "-t 'bufferbloat test' "
            + "-o result.png")
    p.fetch(src="result.png",
            dest="result")
