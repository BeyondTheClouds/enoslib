import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

isolated_net = en.G5kNetworkConf(type="kavlan-local", roles=["isolated"], site="nantes")

conf = (
    en.G5kConf.from_settings(
        job_name=job_name,
        job_type=["deploy"],
        env_name="debian11-nfs",
        walltime="0:20:00",
    )
    .add_network_conf(isolated_net)
    .add_machine(
        roles=["roleA"], cluster="ecotype", nodes=1, primary_network=isolated_net
    )
    .finalize()
)

provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()

# Show local kavlan subnet
print("Kavlan subnet:", networks["isolated"][0].network)

# EnOSlib automatically uses a SSH jump to access the host remotely, so we
# can run commands.  However, the node has no network connectivity with
# the outside world.
results = en.run_command("ping -c 3 -n 9.9.9.9 || true", roles=roles["roleA"])
for result in results:
    print(f"{result.stdout}")


# Release all Grid'5000 resources
provider.destroy()
