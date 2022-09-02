# Chameleon User Guide: Edge to Cloud
# This example is based on:
# https://www.chameleoncloud.org/experiment/share/37991779-fd7b-4ab0-8d6f-e726a9204946

from ipaddress import IPv6Interface
import logging
import enoslib as en
import os

en.init_logging(level=logging.INFO)

prefix = os.getlogin()
_walltime = "02:00:00"

# Leasing resources on G5K
g5k_conf = {
    "walltime": _walltime,
    "job_type": "allow_classic_ssh",
    "job_name": f"{prefix}-enoslib-g5kcloud-lease",
    "resources": {
        "machines": [
            {
                "roles": ["server"],
                "cluster": "paravance",
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
g5k_conf = en.G5kConf.from_dictionnary(g5k_conf)
g5k = en.G5k(g5k_conf)

# Leasing resources on FIT IoT LAB
iotlab_conf = {
    "walltime": _walltime,
    "job_name": f"{prefix}-enoslib-iotlab-lease",
    "resources": {
        "machines": [
            {
                "roles": ["client"],
                "archi": "rpi3:at86rf233",
                "site": "grenoble",
                "number": 1,
            }
        ]
    }
}
iotlab_conf = en.IotlabConf.from_dictionnary(iotlab_conf)
iotlab = en.Iotlab(iotlab_conf)

providers = en.Providers([g5k, iotlab])
roles, networks = providers.init()

g5k, iotlab = providers.providers

# Firewall rules
g5k.fw_create(
    hosts=roles["server"],
    port=[1883],
    src_addr=None,
    proto="tcp+udp"
)

en.run("dhclient -6 br0", roles=roles["server"])
roles = en.sync_info(roles, networks)

cloud_server = roles["server"][0]
addresses = cloud_server.filter_addresses(networks=networks["my_network"])
# get only the ipv6 address
floating_ip = [str(a.ip.ip) for a in addresses if isinstance(a.ip, IPv6Interface)][0]

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
    p.shell(f"bash {dest_dir}/artifacts_edge/edge_worker.sh edge_data 100 {floating_ip}")

# How to check execution?
# firewall rule: https://api.grid5000.fr/stable/sites/rennes/firewall/1909896
# ssh to the Cloud server: ssh root@paravance-40.rennes.grid5000.fr
# root@paravance-40:~# tail -f /tmp/predict.log
# you may also check mosquitto topic (mosquitto_sub_img.py downloads images received in running dir):
# (venv) drosendo@frennes:~$ python mosquitto_sub_img.py --topic edge_data --mqtt_broker 2001:660:4406:700:1::28
# (venv) drosendo@grenoble:~$ python mosquitto_sub_img.py --topic edge_data --mqtt_broker 2001:660:4406:700:1::28
