import logging
from pathlib import Path

import enoslib as en
from enoslib.service.emul.utils import _validate


logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name

# claim the resources
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site="lille")

conf = (
    en.G5kConf.from_settings(job_type="allow_classic_ssh", job_name=job_name)
    .add_network_conf(network)
    .add_machine(roles=["control"], cluster="chiclet", nodes=8, primary_network=network)
    .finalize()
)


provider = en.G5k(conf)
roles, networks = provider.init()

_validate(roles, "_tmp_enos", [h.address for h in roles["control"]])
provider.destroy()
