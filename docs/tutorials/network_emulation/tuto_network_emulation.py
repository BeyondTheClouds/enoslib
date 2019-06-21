from enoslib.api import discover_networks
from enoslib.infra.enos_vmong5k.provider import VMonG5k
from enoslib.infra.enos_vmong5k.configuration import Configuration
from enoslib.service import Netem

import logging
import os

logging.basicConfig(level=logging.DEBUG)


CITIES = {
    "amsterdam": {
        "amsterdam": 0.3,
        "brussels": 14,
        "copenhagen": 18,
        "dusseldorf": 12,
        "geneva": 20,
        "london": 9,
        "lyon": 24,
        "marseille": 40,
        "paris": 26,
        "strasbourg": 13,
        "edimburgh": 19
    },
    "brussels": {
        "brussels": 0.3,
        "copenhagen": 16,
        "dusseldorf": 14,
        "geneva": 20,
        "london": 10,
        "lyon": 14,
        "marseille": 16,
        "paris": 8,
        "strasbourg": 24,
        "edimburgh": 17
    },
    "copenhagen": {
        "copenhagen": 0.3,
        "dusseldorf": 15,
        "geneva": 30,
        "london": 20,
        "lyon": 25,
        "marseille": 35,
        "paris": 22,
        "strasbourg": 27,
        "edimburgh": 31
    },
    "dusseldorf": {
        "dusseldorf": 0.3,
        "geneva": 15,
        "london": 15,
        "lyon": 25,
        "marseille": 20,
        "paris": 10,
        "strasbourg": 22,
        "edimburgh": 22
    },
    "geneva": {
        "geneva": 0.3,
        "london": 18,
        "lyon": 12,
        "marseille": 10,
        "paris": 36,
        "strasbourg": 20,
        "edimburgh": 28
    },
    "london": {
        "london": 0.3,
        "lyon": 14,
        "marseille": 38,
        "paris": 4,
        "strasbourg": 21,
        "edimburgh":10
    },
    "lyon": {
        "lyon": 0.3,
        "marseille": 24,
        "paris": 16,
        "strasbourg": 16,
        "edimburgh": 25
    },
    "marseille": {
        "marseille": 0.3,
        "paris": 25,
        "strasbourg": 30,
        "edimburgh": 27
    },
    "paris": {
        "paris": 0.3,
        "strasbourg": 12,
        "edimburgh": 13
    },
    "strasbourg": {
        "strasbourg": 0.3,
        "edimburgh": 30
    },
    "edimburgh": {
        "edimburgh": 0.3
    }
}

# Building the configuration
conf = Configuration.from_settings(job_name="tuto-vmong5k-netem",
                                   image="/grid5000/virt-images/debian9-x64-base-2019040916.qcow2",
                                   gateway="access.grid5000.fr",
                                   gateway_user="msimonin")
cities = list(CITIES.keys())
for city in cities:
    conf.add_machine(roles=[city],
                     cluster="parasilo",
                     number=1,
                     flavour="tiny")
conf.finalize()

# Starting the machnes
provider = VMonG5k(conf)
roles, networks = provider.init()

# Building the network constraints
emulation_conf = {
    "enable": True,
    "default_delay": "0.3ms",
    "default_rate": "1gbit",
    "groups": cities
}

# Building the specific constraints
constraints = []
for city, others in CITIES.items():
    for other, delay in others.items():
        constraints.append({
            "src": city,
            "dst": other,
            "delay": "%sms" % delay,
            "symetric": True
        })
emulation_conf["constraints"] = constraints

logging.info(emulation_conf)
discover_networks(roles, networks)
netem = Netem(emulation_conf, roles=roles)
netem.deploy()
netem.validate()
