import logging
import tarfile
from pathlib import Path

import enoslib as en
from scapy.all import rdpcap

logging.basicConfig(level=logging.INFO)


CLUSTER = "parasilo"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

# claim the resources
conf = en.G5kConf.from_settings(job_type="allow_classic_ssh", job_name=job_name)
network = en.G5kNetworkConf(id="n1", type="prod", roles=["my_network"], site=SITE)
conf.add_network_conf(network).add_machine(
    roles=["control", "client"], cluster=CLUSTER, nodes=1, primary_network=network
).add_machine(
    roles=["control", "server"], cluster=CLUSTER, nodes=1, primary_network=network
).finalize()

provider = en.G5k(conf)
roles, networks = provider.init()

roles = en.sync_info(roles, networks)

# start a capture
# - on all the interface configured on the my_network network
# - we dump icmp traffic only
# - for the duration of the commands (here a client is pigging the server)
with en.TCPDump(
    hosts=roles["control"], networks=networks["my_network"], options="icmp"
) as t:
    backup_dir = t.backup_dir
    _ = en.run(f"ping -c10 {roles['server'][0].address}", roles["client"])

# pcap files are retrieved in the __enoslib__tcpdump__ directory
# - can be loaded in wireshark
# - manipulated with scappy ...


# Examples:
# create a dictionary of (alias, if) -> list of decoded packets by scapy
decoded_pcaps = {}
for host in roles["control"]:
    host_dir = backup_dir / host.alias
    t = tarfile.open(host_dir / "tcpdump.tar.gz")
    t.extractall(host_dir / "extracted")
    # get all extracted pcap for this host
    pcaps = (host_dir / "extracted").rglob("*.pcap")
    for pcap in pcaps:
        decoded_pcaps.setdefault(
            (host.alias, pcap.with_suffix("").name), rdpcap(str(pcap))
        )

# Displaying some packets
for (host, ifs), packets in decoded_pcaps.items():
    print(host, ifs)
    packets[0].show()
    packets[1].show()
