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
        roles=["server"],
        cluster="parasilo",
        nodes=1,
        secondary_networks=[private_net],
    )
    .add_machine(
        roles=["client"],
        cluster="parasilo",
        nodes=1,
        secondary_networks=[private_net],
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Fill in network information from nodes
roles = en.sync_info(roles, networks)

# Get server's IP address on the private network
server = roles["server"][0]
ip_address_obj = server.filter_addresses(networks=networks["private"])[0]
# This may seem weird: ip_address_obj.ip is a `netaddr.IPv4Interface`
# which itself has an `ip` attribute.
server_private_ip = ip_address_obj.ip.ip

# Run ping from client to server on the private network
results = en.run_command(f"ping -c3 {server_private_ip}", roles=roles["client"])
for result in results:
    print(f"Ping from {result.host} to {server_private_ip}:")
    print(f"{result.stdout}")


# Release all Grid'5000 resources
provider.destroy()
