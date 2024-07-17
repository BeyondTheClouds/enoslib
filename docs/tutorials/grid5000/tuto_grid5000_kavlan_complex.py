import json
import logging
from pathlib import Path

import enoslib as en
from enoslib.infra.enos_g5k.objects import G5kEnosVlan6Network

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

# Topology goal:
# (Nantes nodes) --- (node1.nancy) --- (node2.nancy) --- (Rennes nodes)

# The site doesn't really matter, but let's be consistent with nodes
kavlan_global1 = en.G5kNetworkConf(
    type="kavlan-global",
    roles=["global1"],
    site="rennes",
)
kavlan_global2 = en.G5kNetworkConf(
    type="kavlan-global",
    roles=["global2"],
    site="nantes",
)
# Internal VLAN in Nancy
nancy_kavlan = en.G5kNetworkConf(type="kavlan-local", roles=["nancy"], site="nancy")
# Default network for nancy (see below)
nancy_prod = en.G5kNetworkConf(type="prod", roles=["prod"], site="nancy")

# Request nodes from Rennes, Nantes and Nancy
conf = (
    en.G5kConf()
    .from_settings(
        job_type=["deploy"],
        env_name="debian11-nfs",
        job_name=job_name,
        walltime="00:30:00",
    )
    .add_network_conf(kavlan_global1)
    .add_network_conf(kavlan_global2)
    .add_network_conf(nancy_kavlan)
    .add_network_conf(nancy_prod)
    .add_machine(
        roles=["rennes"],
        cluster="paravance",
        nodes=2,
        secondary_networks=[kavlan_global1],
    )
    .add_machine(
        roles=["nantes"],
        cluster="econome",
        nodes=2,
        secondary_networks=[kavlan_global2],
    )
    # These two nodes in Nancy will act as routers: one as a gateway for
    # Rennes nodes, one as a gateway for Nantes nodes.
    .add_machine(
        roles=["nancy", "router", "gw-rennes"],
        cluster="grisou",
        nodes=1,
        # Demonstrates how to choose the correct physical network
        # interfaces.  Here, we assume we specifically want to use the
        # Intel X520 NIC on grisou:
        #
        # https://www.grid5000.fr/w/Nancy:Hardware#grisou
        #
        # To do this, we specify that "eth1" should simply use the regular
        # network, while "eth2" and "eth3" are configured with our kavlan
        # networks.
        secondary_networks=[nancy_prod, kavlan_global1, nancy_kavlan],
    )
    .add_machine(
        roles=["nancy", "router", "gw-nantes"],
        cluster="grisou",
        nodes=1,
        secondary_networks=[nancy_prod, kavlan_global2, nancy_kavlan],
    )
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Fill in network information from nodes
roles = en.sync_info(roles, networks)


# Helper functions
def get_ip(node, nets):
    """Returns the IPv4 address of the given node on the given network"""
    addresses = node.filter_addresses(networks=nets)
    if len(addresses) == 0:
        raise ValueError(f"Cannot determine IP address of node in nets: {node.address}")
    ip_address_obj = addresses[0]
    return ip_address_obj.ip.ip


def display_results(results):
    for result in results:
        print(f"# {result.host}")
        print(f"{result.stdout}")


gw_rennes = roles["gw-rennes"][0]
gw_nantes = roles["gw-nantes"][0]
# For each group, define which routes need to be added, and which nexthop
# will be used for these routes.
routes = {
    "rennes": networks["nancy"] + networks["global2"],
    "nantes": networks["nancy"] + networks["global1"],
    "gw-rennes": networks["global2"],
    "gw-nantes": networks["global1"],
}
nexthops = {
    "rennes": get_ip(gw_rennes, networks["global1"]),
    "nantes": get_ip(gw_nantes, networks["global2"]),
    "gw-rennes": get_ip(gw_nantes, networks["nancy"]),
    "gw-nantes": get_ip(gw_rennes, networks["nancy"]),
}

# Setup actual routes
for group in routes.keys():
    with en.actions(roles=roles[group]) as p:
        nexthop = nexthops[group]
        for net in routes[group]:
            # No automatic IPv6 for now
            if isinstance(net, G5kEnosVlan6Network):
                continue
            subnet = net.network
            # Use "replace" instead of "add" to ensure indempotency
            cmd = f"ip route replace {subnet} via {nexthop}"
            p.command(cmd, task_name=f"route {subnet} via {nexthop}")

# Enable IP forwarding on routers
en.run_command("sysctl net.ipv4.ip_forward=1", roles=roles["router"])

# Test connectivity from Rennes to Nancy
target = get_ip(gw_nantes, networks["nancy"])
cmd = f"ping -c 3 {target}"
results = en.run_command(cmd, task_name=cmd, roles=roles["rennes"])
display_results(results)

# Test connectivity from Nantes to Nancy
target = get_ip(gw_rennes, networks["nancy"])
cmd = f"ping -c 3 {target}"
results = en.run_command(cmd, task_name=cmd, roles=roles["nantes"])
display_results(results)

# Test connectivity from Nantes to Rennes, check latency and TTL.
# We install pythonping and use it in a small python script to avoid
# parsing ping output.
pingscript = """
import json
import sys
import pythonping
res = pythonping.ping(sys.argv[1], interval=1, count=3)
answer = list(res)[0]
# pythonping does not expose the TTL, but we can access the raw IP header
ttl = answer.message.packet.raw[8]
display = dict(ttl=ttl, rtt_min_ms=res.rtt_min_ms)
print(json.dumps(display))
"""
target_nodes = roles["rennes"]
targets = [get_ip(node, networks["global1"]) for node in target_nodes]
with en.actions(roles=roles["nantes"]) as p:
    p.apt(name="python3-pip")
    p.pip(name="pythonping>=1.1.4,<1.2")
    p.copy(dest="/tmp/ping.py", content=pingscript)
    for target in targets:
        p.command(f"python3 /tmp/ping.py {target}", task_name=f"ping {target}")

results = p.results

# Print all pairs of pings and check validity
for (target_node, target) in zip(target_nodes, targets):
    for res in results.filter(task=f"ping {target}"):
        print(f"# {res.host} -> {target_node.address} via Nancy")
        data = json.loads(res.stdout)
        print(f"TTL = {data['ttl']}")
        print(f"Min RTT = {data['rtt_min_ms']} ms")
        print()
        assert data["ttl"] == 62
        assert data["rtt_min_ms"] >= 20


# Release all Grid'5000 resources
provider.destroy()
