import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "name_prefix": "basic-example",
    "rc_file": "secrets/fabric_rc",
    "walltime": "02:00:00",
    "site": "FIU",
    "image": "default_ubuntu_22",
    "resources": {
        "machines": [
            {
                "roles": ["CloudOne"],
                "site": "UCSD",
                "image": "default_rocky_9",
                "flavour": "large",
                "number": 1,
            },
            {
                "roles": ["CloudTwo"],
                "flavour_desc": {
                    "core": 4,
                    "mem": 4,
                    "disk": 10,
                },
                "number": 1,
            },
        ],
        "networks": [
            {
                "roles": ["n1"],
                "kind": "FABNetv4",
                "site": "FIU",
                "nic": {
                    "kind": "SharedNIC",
                    "model": "ConnectX-6",
                },
            },
            {
                "roles": ["n1"],
                "kind": "FABNetv4",
                "site": "UCSD",
                "nic": {
                    "kind": "SharedNIC",
                    "model": "ConnectX-6",
                },
            },
        ],
    },
}

# claim the resources
conf = en.FabricConf.from_dictionary(provider_conf)
provider = en.Fabric(conf)
roles, networks = provider.init()
print(roles)
print(networks)

# destroy the boxes
provider.destroy()
