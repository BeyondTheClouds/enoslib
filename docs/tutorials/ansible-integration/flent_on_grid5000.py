from pathlib import Path

import enoslib as en

logging = en.init_logging()

CLUSTER = "ecotype"
SITE = en.g5k_api_utils.get_cluster_site(CLUSTER)

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name)
    .add_machine(roles=["server"], cluster=CLUSTER, nodes=1)
    .add_machine(roles=["client"], cluster=CLUSTER, nodes=1)
)

provider = en.G5k(conf)
roles, networks = provider.init()

with en.actions(roles=roles) as p:
    p.apt(
        name=["flent", "netperf", "python3-setuptools", "python3-matplotlib"],
        state="present",
        update_cache="yes",
    )

with en.actions(pattern_hosts="server", roles=roles) as p:
    p.shell("nohup netperf &")

with en.actions(pattern_hosts="client", roles=roles) as p:
    server_address = roles["server"][0].address
    p.shell(
        "flent rrul -p all_scaled "
        + "-l 60 "
        + f"-H { server_address } "
        + "-t 'bufferbloat test' "
        + "-o result.png"
    )
    p.fetch(src="result.png", dest="result")


# Release resources
provider.destroy()
