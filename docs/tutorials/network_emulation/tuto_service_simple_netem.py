import logging

from enoslib import *

logging.basicConfig(level=logging.DEBUG)


prod_network = G5kNetworkConf(
    id="n1",
    type="prod",
    roles=["my_network"],
    site="rennes"
)
conf = (
    G5kConf.from_settings(job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_machine(
        roles=["city", "paris"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="parapluie",
        nodes=1,
        primary_network=prod_network
    )
    .finalize()
)
provider = G5k(conf)
roles, networks = provider.init()
roles = sync_info(roles, networks)

netem = SimpleNetem("delay 10ms", hosts=roles["city"], networks=networks["my_network"])
netem.deploy()
netem.validate()
netem.destroy()
