import logging

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

conf = (
    en.G5kConf.from_settings(job_type=[], walltime="01:00:00")
    .add_machine(
        roles=["city", "paris"],
        cluster="parasilo",
        nodes=1,
    )
    .add_machine(
        roles=["city", "berlin"],
        cluster="parasilo",
        nodes=1,
    )
    .add_machine(
        roles=["city", "londres"],
        cluster="parasilo",
        nodes=1,
    )
)
provider = en.G5k(conf)
roles, networks = provider.init()
roles = en.sync_info(roles, networks)

netem = en.Netem()
(
    netem.add_constraints("delay 10ms", roles["paris"], symmetric=True)
    .add_constraints("delay 20ms", roles["londres"], symmetric=True)
    .add_constraints("delay 30ms", roles["berlin"], symmetric=True)
)

netem.deploy()
netem.validate()
netem.destroy()

for role, hosts in roles.items():
    print(role)
    for host in hosts:
        print(f"-- {host.alias}")
