# Chameleon User Guide: Edge to Cloud
# This example is based on:
# https://www.chameleoncloud.org/experiment/share/37991779-fd7b-4ab0-8d6f-e726a9204946

import logging
import time
import enoslib as en
import os

en.init_logging(level=logging.INFO)
logging.basicConfig(level=logging.INFO)

prefix = os.getlogin()
_walltime = "02:00:00"
providers = []
# Leasing resources on Chameleon Cloud
provider_conf = {
    "walltime": _walltime,
    "lease_name": f"{prefix}-enoslib-chicloud-lease",
    "rc_file": "./my-app-cred-cloud-openrc.sh",  # FIXME use your OPENRC file
    "key_name": "drosendo",  # FIXME use your key_name
    "image": "CC-Ubuntu20.04",
    "resources": {
        "machines": [
            {
                "roles": ["server"],
                "flavour": "gpu_rtx_6000",
                "number": 1,
            }
        ],
        "networks": ["network_interface"],
    },
}
conf = en.CBMConf().from_dictionnary(provider_conf)
provider = en.CBM(conf)
roles, networks = provider.init()
providers.append(provider)
roles = en.sync_info(roles, networks)
floating_ip = roles["server"][0].extra["gateway"]  # 192.5.87.127

# Leasing resources on Chameleon Edge
provider_conf = {
    "walltime": _walltime,
    "lease_name": f"{prefix}-enoslib-chiedge-lease",
    "rc_file": "./my-app-cred-edge-openrc.sh",  # FIXME use your OPENRC file
    "resources": {
        "machines": [
            {
                "roles": ["client"],
                "device_name": "iot-rpi4-03",
                "container": {
                    "name": "cli-container",
                    "image": "arm64v8/ubuntu",
                },
            }
        ],
    },
}
conf = en.ChameleonEdgeConf.from_dictionnary(provider_conf)
provider = en.ChameleonEdge(conf)
roles_edge, networks_edge = provider.init()
providers.append(provider)

# Merging Chameleon Cloud and Edge resources
for role, hosts in roles_edge.items():
    roles[role] = hosts
logging.info("*" * 40 + f" roles{type(roles)} = {roles}")
logging.info("*" * 40 + f" networks{type(networks)} = {networks}")

# Experimentation logic starts here
# Chameleon Cloud
dest_dir = "/tmp"
with en.play_on(roles=roles["server"]) as p:
    p.copy(src="./artifacts_cloud/", dest=dest_dir)
    p.shell(f"cd {dest_dir} && bash {dest_dir}/cloud_worker.sh > {dest_dir}/tests")
# Chameleon Edge
for device in roles["client"]:
    cmd_upload = device.upload("./artifacts_edge/", "/")
    cmd_execute = device.execute(f"bash /edge_worker.sh edge_data 100 {floating_ip}")

logging.info("Running experiment for 600 secs...")
time.sleep(600)
# How to check execution?  ssh to the Cloud server: ssh cc@<floating_ip>
# cc@<floating_ip>:~# tail -f /tmp/predict.log you may also check mosquitto
# topic (mosquitto_sub_img.py downloads images received in running dir):

# $) python mosquitto_sub_img.py --topic edge_data --mqtt_broker 192.5.87.127

# Releasing resources from Chameleon Cloud and Edge
logging.info("Releasing resources.")
for p in providers:
    p.destroy()
