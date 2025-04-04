# Edge to Cloud example with Iot-Lab and Grid'5000
# This example is inspired from:
# https://www.chameleoncloud.org/experiment/share/37991779-fd7b-4ab0-8d6f-e726a9204946

import logging
import os
from ipaddress import IPv6Interface

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

prefix = os.getlogin()
_walltime = "02:00:00"

JOB_NAME = f"{prefix}-enoslib-g5kcloud-lease3"

# Leasing resources on G5K
g5k_conf = {
    "walltime": _walltime,
    "job_type": [],
    "job_name": JOB_NAME,
    "resources": {
        "machines": [
            {
                "roles": ["server"],
                "cluster": "paradoxe",
                "nodes": 1,
                "primary_network": "n1",
                "secondary_networks": [],
            },
        ],
        "networks": [
            {"id": "n1", "type": "prod", "roles": ["my_network"], "site": "rennes"}
        ],
    },
}
g5k_conf = en.G5kConf.from_dictionary(g5k_conf)
g5k = en.G5k(g5k_conf)

# Leasing resources on FIT IoT LAB
iotlab_conf = {
    "walltime": _walltime,
    "job_name": JOB_NAME,
    "resources": {
        "machines": [
            {
                "roles": ["client"],
                "archi": "rpi3:at86rf233",
                "site": "grenoble",
                "number": 3,
            }
        ]
    },
}
iotlab_conf = en.IotlabConf.from_dictionary(iotlab_conf)
iotlab = en.Iotlab(iotlab_conf)

providers = en.Providers([g5k, iotlab])
roles, networks = providers.init()

# Firewall rules
with g5k.firewall(hosts=roles["server"], port=[1883], src_addr=None, proto="tcp+udp"):
    en.run("dhclient -6 br0", roles=roles["server"])
    roles = en.sync_info(roles, networks)

    cloud_server = roles["server"][0]
    addresses = cloud_server.filter_addresses(networks=networks["my_network"])
    # get only the ipv6 address
    floating_ip = [str(a.ip.ip) for a in addresses if isinstance(a.ip, IPv6Interface)][
        0
    ]

    logging.info(f"Cloud server IP: {floating_ip}")  # 2001:660:4406:700:1::28

    # Experimentation logic starts here
    # G5K Cloud
    dest_dir = "/tmp"
    with en.play_on(roles=roles["server"]) as p:
        p.copy(src="./artifacts_cloud/", dest=dest_dir)
        p.shell(f"cd {dest_dir} && bash {dest_dir}/cloud_worker.sh > {dest_dir}/tests")
    # FIT IoT LAB
    with en.play_on(roles=roles["client"]) as p:
        p.copy(src="./artifacts_edge", dest=dest_dir)
        p.shell(
            f"bash {dest_dir}/artifacts_edge/edge_worker.sh edge_data 100 {floating_ip}"
        )

    # How to check execution?  firewall rule:
    # https://api.grid5000.fr/stable/sites/rennes/firewall/1909896 ssh to the
    # Cloud server: ssh root@paradoxe-3.rennes.grid5000.fr
    # root@paradoxe-3:~# tail -f /tmp/predict.log you may also check mosquitto
    # topic (mosquitto_sub_img.py downloads images received in running dir):

    # $ python mosquitto_sub_img.py --topic edge_data --mqtt_broker <IPv6>
    # $ python mosquitto_sub_img.py --topic edge_data --mqtt_broker <IPv6>
