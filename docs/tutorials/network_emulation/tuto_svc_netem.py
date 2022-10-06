import logging

import enoslib as en

logging.basicConfig(level=logging.DEBUG)


prod_network = en.G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    en.G5kConf.from_settings(job_type=[], walltime="01:00:00")
    .add_network_conf(prod_network)
    .add_machine(
        roles=["city", "paris"],
        cluster="paravance",
        nodes=1,
        primary_network=prod_network,
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="paravance",
        nodes=1,
        primary_network=prod_network,
    )
    .add_machine(
        roles=["city", "londres"],
        cluster="paravance",
        nodes=1,
        primary_network=prod_network,
    )
    .finalize()
)
provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)

netem = en.Netem()
(
    netem.add_constraints("delay 10ms", roles["paris"], symetric=True)
    .add_constraints("delay 20ms", roles["londres"], symetric=True)
    .add_constraints("delay 30ms", roles["berlin"], symetric=True)
)

netem.deploy()
netem.validate()
netem.destroy()

for role, hosts in roles.items():
    print(role)
    for host in hosts:
        print(f"-- {host.alias}")
