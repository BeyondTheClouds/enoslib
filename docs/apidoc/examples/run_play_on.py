import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "resources": {
        "machines": [{
            "roles": ["control"],
            "flavour": "tiny",
            "number": 1,
        },{
            "roles": ["client"],
            "flavour": "tiny",
            "number": 1,
        }],
        "networks": [{"roles": ["rn1"], "cidr": "172.16.0.1/16"}]
    }
}

conf = VagrantConf.from_dictionnary(provider_conf)
provider = Vagrant(conf)
roles, networks = provider.init()

with play_on(roles=roles) as p:
    p.debug(msg="{{ inventory_hostname  }}")

with play_on(pattern_hosts="client", roles=roles) as p:
    p.debug(msg="{{ inventory_hostname  }}")
    # this fails
    # p.debug(msg="{{ hostvars[groups['control'][0]].ansible_fqdn }}")

with play_on(pattern_hosts="control", roles=roles) as p:
    p.debug(msg="{{ inventory_hostname  }}")

with play_on(pattern_hosts="client", roles=roles, gather_facts="control") as p:
    p.debug(msg="{{ inventory_hostname  }}")
    # This doesn't fail because we gather facts on the control host
    p.debug(msg="{{ hostvars[groups['control'][0]].ansible_fqdn }}")

with play_on(pattern_hosts="client", roles=roles, gather_facts="all") as p:
    p.debug(msg="{{ inventory_hostname  }}")
    # This doesn't fail because we gather facts on all hosts
    p.debug(msg="{{ hostvars[groups['control'][0]].ansible_fqdn }}")
