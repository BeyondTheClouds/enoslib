import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

private_net = en.G5kNetworkConf(type="kavlan", roles=["private"], site="rennes")

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        job_type=["deploy"],
        env_name="debian11-nfs",
        walltime="0:20:00",
    )
    .add_network_conf(private_net)
    .add_machine(
        roles=["roleA"], cluster="parasilo", nodes=2, primary_network=private_net
    )
    .finalize()
)

provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()

# Show kavlan subnet
print("Kavlan subnet:", networks["private"][0].network)

# The nodes use this kavlan network for all traffic
# (the network is interconnected at layer-3 with the rest of Grid'5000)
results = en.run_command("ip route get 9.9.9.9", roles=roles["roleA"])
for result in results:
    print(f"{result.stdout}")


# Release all Grid'5000 resources
provider.destroy()
