import logging

import enoslib as en

logging.basicConfig(level=logging.INFO)

provider_conf = {
    "backend": "libvirt",
    "resources": {
        "machines": [
            {
                "roles": ["master"],
                "flavour": "tiny",
                "number": 1,
            },
            {
                "roles": ["agent"],
                "flavour": "tiny",
                "number": 1,
            },
        ],
        "networks": [{"roles": ["r1"], "cidr": "172.16.42.0/16"}],
    },
}

conf = en.VagrantConf.from_dictionary(provider_conf)
provider = en.Vagrant(conf)
roles, networks = provider.init()

roles = en.sync_info(roles, networks)

locust = en.Locust(
    master=roles["master"][0],
    workers=roles["agent"],
    networks=networks["r1"],
    local_expe_dir="expe",
    run_time=100,
)

locust.deploy()
locust.backup()
