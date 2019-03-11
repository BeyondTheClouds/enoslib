from enoslib.api import discover_networks, play_on
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging


logging.basicConfig(level=logging.DEBUG)

conf = Configuration.from_settings(backend="libvirt",
                                   box="generic/debian9")\
                    .add_machine(roles=["server"],
                                 flavour="tiny",
                                 number=1)\
                    .add_machine(roles=["client"],
                                 flavour="tiny",
                                 number=1)\
                    .add_network(roles=["mynetwork"],
                                 cidr="192.168.42.0/24")

provider = Enos_vagrant(conf)
roles, networks = provider.init()
discover_networks(roles, networks)
with play_on("all", roles=roles) as p:
    p.apt_repository(repo="deb http://deb.debian.org/debian stretch main contrib non-free",
                     state="present")
    p.apt(name=["flent", "netperf"],
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
