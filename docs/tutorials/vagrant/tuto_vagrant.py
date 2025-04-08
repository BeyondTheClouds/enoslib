import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "backend": "libvirt",
    "box": "bento/ubuntu-22.04",
    "name_prefix": "vm",
    "config_extra": 'config.vm.synced_folder ".", "/vagrant", disabled: true',
    "resources": {
        "machines": [
            {
                "roles": ["CloudOne"],
                "name_prefix": "CloudOne",
                "backend": "virtualbox",
                "box": "bento/rockylinux-9",
                "flavour": "large",
                "config_extra_vm": """my.vm.synced_folder "./bin", "/vagrant/bin"
my.vm.synced_folder "./data", "/vagrant/data" """,
            },
            {
                "roles": ["CloudTwo"],
                "number": 1,
                "flavour": "large",
            },
        ],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}],
    },
}

# claim the resources
conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()
print(roles)
print(networks)

# destroy the boxes
provider.destroy()
