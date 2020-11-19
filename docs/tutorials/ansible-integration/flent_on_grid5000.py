from enoslib import *

import logging


logging.basicConfig(level=logging.DEBUG)

network = G5kNetworkConf(
    id="n1",
    type="kavlan",
    roles=["mynetwork"],
    site="rennes"
)

conf = (
    G5kConf
    .from_settings(job_name=__file__)
    .add_network_conf(network)
    .add_machine(
        roles=["server"],
        cluster="parapluie",
        nodes=1,
        primary_network=network
    )
    .add_machine(
        roles=["client"],
        cluster="parapluie",
        nodes=1,
        primary_network=network
    )
    .finalize()
)

provider = G5k(conf)
roles, networks = provider.init()
roles = discover_networks(roles, networks)
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
    p.shell("flent rrul -p all_scaled "
            + "-l 60 "
            + "-H {{ hostvars[groups['server'][0]].ansible_default_ipv4.address }} "
            + "-t 'bufferbloat test' "
            + "-o result.png")
    p.fetch(src="result.png",
            dest="result")
