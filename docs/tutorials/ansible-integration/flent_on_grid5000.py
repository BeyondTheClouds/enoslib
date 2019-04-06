from enoslib.api import discover_networks, play_on
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_g5k.configuration import (Configuration,
                                                  NetworkConfiguration)

import logging


logging.basicConfig(level=logging.DEBUG)

network = NetworkConfiguration(id="n1",
                               type="kavlan",
                               roles=["mynetwork"],
                               site="rennes")
conf = Configuration.from_settings(job_name="flent_on",
                                  env_name="debian9-x64-std")\
                    .add_network_conf(network)\
                    .add_machine(roles=["server"],
                                 cluster="parapluie",
                                 nodes=1,
                                 primary_network=network)\
                    .add_machine(roles=["client"],
                                 cluster="parapluie",
                                 nodes=1,
                                 primary_network=network)\
                    .finalize()

provider = G5k(conf)
roles, networks = provider.init()
discover_networks(roles, networks)
with play_on("all", roles=roles) as p:
    # flent requires python3, so we default python to python3
    p.shell("update-alternatives --install /usr/bin/python python /usr/bin/python3 1")
    p.apt_repository(repo="deb http://deb.debian.org/debian stretch main contrib non-free",
                     state="present")
    p.apt(name=["flent", "netperf", "python3-setuptools"],
          state="present")

with play_on("server", roles=roles) as p:
    p.shell("nohup netperf &")

with play_on("client", roles=roles) as p:
    p.shell("flent rrul -p all_scaled "
            + "-l 60 "
            + "-H {{ hostvars[groups['server'][0]].inventory_hostname }} "
            + "-t 'bufferbloat test' "
            + "-o result.png")
    p.fetch(src="result.png",
            dest="result")
