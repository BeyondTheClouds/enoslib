import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["client"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}],
    }
}

conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)

roles, networks = provider.init()

with en.actions(roles=roles) as p:
    p.debug(msg="{{ inventory_hostname  }}")

with en.actions(pattern_hosts="client", roles=roles) as p:
    p.debug(msg="{{ inventory_hostname  }}")

# Using the actions wrapper allows for using a list of hosts instead of a Roles object
with en.actions(roles=roles["client"]) as p:
    p.debug(msg="{{ inventory_hostname  }}")

with en.actions(roles=roles["client"], gather_facts=True) as p:
    p.debug(msg="{{ inventory_hostname  }}")


with en.actions(roles=roles["client"], gather_facts=False) as p:
    p.debug(msg="{{ inventory_hostname  }}")
    p.shell("sleep 3")
    p.shell("sleep 5", background=True)
    p.shell("sleep 3")


with en.actions(roles=roles["client"], gather_facts=False, background=True) as p:
    p.debug(msg="{{ inventory_hostname  }}", background=False)
    p.shell("sleep 3")
    p.shell("sleep 5", background=False)
    p.shell("sleep 3")
