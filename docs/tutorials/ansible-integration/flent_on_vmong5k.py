from enoslib.api import discover_networks, play_on
from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration

import logging


logging.basicConfig(level=logging.DEBUG)

conf = Configuration.from_settings(job_name="flent_on",
                                   image="/grid5000/virt-images/debian9-x64-std-2019040916.qcow2",
                                   gateway="access.grid5000.fr",
                                   gateway_user="msimonin")\
                    .add_machine(roles=["server"],
                                 cluster="grisou",
                                 number=1)\
                    .add_machine(roles=["client"],
                                 cluster="grisou",
                                 number=1)\
                    .finalize()

provider = VMonG5k(conf)

roles, networks = provider.init()
discover_networks(roles, networks)
with play_on(roles=roles) as p:
    # flent requires python3, so we default python to python3
    p.shell("update-alternatives --install /usr/bin/python python /usr/bin/python3 1")
    p.apt_repository(repo="deb http://deb.debian.org/debian stretch main contrib non-free",
                     state="present")
    p.apt(name=["flent", "netperf", "python3-setuptools"],
          state="present")

with play_on(pattern_hosts="server", roles=roles) as p:
    p.shell("nohup netperf &")

with play_on(pattern_hosts="client", roles=roles) as p:
    p.shell("flent rrul -p all_scaled "
            + "-l 60 "
            + "-H {{ hostvars[groups['server'][0]].inventory_hostname }} "
            + "-t 'bufferbloat test' "
            + "-o result.png")
    p.fetch(src="result.png",
            dest="result")
