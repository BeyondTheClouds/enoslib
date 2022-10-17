import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)

job_name = Path(__file__).name

# A globlal Kavlan can be reserved on any site
kavlan_global = en.G5kNetworkConf(type="kavlan-global", roles=["global"], site="lille")

# Request nodes from Rennes and Lille
conf = (
    en.G5kConf()
    .from_settings(
        job_type=["deploy"],
        env_name="debian11-nfs",
        job_name=job_name,
        walltime="00:50:00",
    )
    .add_network_conf(kavlan_global)
    .add_machine(
        roles=["rennes", "client"],
        cluster="paravance",
        nodes=1,
        secondary_networks=[kavlan_global],
    )
    .add_machine(
        roles=["lille", "server"],
        cluster="chiclet",
        nodes=1,
        secondary_networks=[kavlan_global],
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Fill in network information from nodes
roles = en.sync_info(roles, networks)

for host in roles["client"] + roles["server"]:
    # Find out which physical interface is connected to Kavlan network
    interfaces = host.filter_interfaces(networks=networks["global"])
    assert len(interfaces) == 1
    interface_name = interfaces[0]
    # Set MTU to 9000
    cmd = f"ip link set {interface_name} mtu 9000"
    en.run_command(cmd, task_name=cmd, roles=host, gather_facts=False)

server = roles["server"][0]
ip_address_obj = server.filter_addresses(networks=networks["global"])[0]
# This may seem weird: ip_address_obj.ip is a `netaddr.IPv4Interface`
# which itself has an `ip` attribute.
server_private_ip = ip_address_obj.ip.ip

# Run ping from client to server on the private network.
# Ensure they are in the same L2 network (TTL=1) and that MTU is 9000.
results = en.run_command(
    f"ping -t 1 -c3 -M do -s 8972 {server_private_ip}", roles=roles["client"]
)
for result in results:
    print(f"Ping from {result.host} to {server_private_ip}:")
    print(f"{result.stdout}")


# Release all Grid'5000 resources
provider.destroy()
