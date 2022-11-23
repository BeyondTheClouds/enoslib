import logging
import os
import time

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

provider_conf = {
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "address": "localhost",
                "alias": "test_machine",
                "extra": {"ansible_connection": "local"},
            }
        ],
        "networks": [
            {
                "roles": ["local"],
                "start": "172.17.0.0",
                "end": "172.17.255.255",
                "cidr": "172.17.0.0/16",
                "gateway": "172.17.0.1",
                "dns": "172.17.0.1",
            }
        ],
    }
}

inventory = os.path.join(os.getcwd(), "hosts")
conf = en.StaticConf.from_dictionary(provider_conf)
provider = en.Static(conf)

roles, networks = provider.init()

roles = en.sync_info(roles, networks)

m = en.Dstat(nodes=roles["control"])
m.deploy()
# stop monitoring to be generated before backuping
time.sleep(10)
m.destroy()
m.backup()

df = en.Dstat.to_pandas(m.backup_dir)
print(df)
assert not df.empty
