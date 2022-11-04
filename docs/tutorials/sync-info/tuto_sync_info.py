import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = en.G5kConf.from_settings(job_type=[], job_name=job_name).add_machine(
    roles=["control"], cluster="paravance", nodes=1
)

provider = en.G5k(conf)
roles, networks = provider.init()

roles_synced = en.sync_info(roles, networks)

# some info has been populated
h = roles_synced["control"][0]
assert len(h.net_devices) > 0
assert h.processor is not None

# we can filter addresses based on a given network (one ipv4 address here)
assert len(h.filter_addresses(networks["my_network"])) >= 1

# add an ipv6 (if not already there)
en.run_command("dhclient -6 br0", roles=roles)

# resync
roles_synced = en.sync_info(roles, networks)
h = roles_synced["control"][0]

# we now have two addresses in the network my_network (one ipv4, one ipv6)
assert len(h.filter_addresses(networks["my_network"])) == 2
