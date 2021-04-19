import logging
from itertools import islice, product
from pathlib import Path

import enoslib as en

logging.basicConfig(level=logging.DEBUG)

job_name = Path(__file__).name


prod_network = en.G5kNetworkConf(
    id="n1", type="prod", roles=["my_network"], site="rennes"
)
conf = (
    en.G5kConf.from_settings(job_name=job_name, job_type="allow_classic_ssh")
    .add_network_conf(prod_network)
    .add_network(
        id="not_linked_to_any_machine",
        type="slash_22",
        roles=["my_subnet"],
        site="rennes",
    )
    .add_machine(
        roles=["control"], cluster="paravance", nodes=10, primary_network=prod_network
    )
    .finalize()
)

provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# distribute some virtual ips :)
N = 100
ips = networks["my_subnet"][0].free_ips
for host in roles["control"]:
    host.extra.update(ips=[str(ip) for ip in islice(ips, N)])
with en.play_on(roles=roles, gather_facts=False) as p:
    p.shell(
        "(ip a | grep {{ item }}) || ip addr add {{ item }}/22 dev br0",
        loop="{{ ips }}",
    )

# All virtual ips being set on the hosts
# let's build the list of constraints
htb_hosts = []
humans = []
for h_idx, (h1, h2) in enumerate(product(roles["control"], roles["control"])):
    # need to account for h1 = h2 to set constraint on loopback device
    htb = en.HTBSource(host=h1)
    ips2 = h2.extra["ips"]
    for ip_idx, ip2 in enumerate(ips2):
        # this is the delay between one machine h1 and any of the virtual ip of h2
        # since h1 and h2 will be swapped in another iteration, we'll also set
        # the "symetrical" at some point.
        delay = 5 * ip_idx
        humans.append(f"({h1.alias}) -->{delay}--> {ip2}({h2.alias}) ")
        if h1 == h2:
            # loopback
            htb.add_constraint(delay=f"{delay}ms", device="lo", target=ip2)
        else:
            htb.add_constraint(delay=f"{delay}ms", device="br0", target=ip2)
    htb_hosts.append(htb)

en.netem_htb(htb_hosts)


Path("htb.list").write_text("\n".join(humans))
# you can check the constraint be issuing some:
# ping -I <ip_source> <ip_dest>
