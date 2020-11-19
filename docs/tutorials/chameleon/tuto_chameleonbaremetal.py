import logging

from enoslib import *

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "key_name": "enos_matt",
    "lease_name": "mylease",
    "resources": {
        "machines": [{
            "roles": ["server"],
            "flavour": "compute_skylake",
            "number": 1,
        },{
            "roles": ["client"],
            "flavour": "compute_skylake",
            "number": 1,
        }],
        "networks": ["network_interface"]
    }
}

tc = {
    "enable": True,
    "default_delay": "20ms",
    "default_rate": "1gbit",
}
conf = CBMConf.from_dictionnary(provider_conf)
provider = CBM(conf)

roles, networks = provider.init()

roles = discover_networks(roles, networks)

# Experimentation logic starts here
with play_on(roles=roles) as p:
    # flent requires python3, so we default python to python3
    p.apt_repository(repo="deb http://deb.debian.org/debian stretch main    contrib non-free",
                     state="absent")
    p.apt(name=["flent", "netperf", "python3-setuptools", "python3-matplotlib"],
          allow_unauthenticated=True,
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
