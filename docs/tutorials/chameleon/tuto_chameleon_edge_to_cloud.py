# Chameleon User Guide: Edge to Cloud
# This example is based on:
# https://www.chameleoncloud.org/experiment/share/37991779-fd7b-4ab0-8d6f-e726a9204946

import logging
import time
import enoslib as en
import os

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
        "machines": [{
            "roles": ["server"],
            "flavour": "gpu_rtx_6000",
            "number": 1,
        }],
        "networks": ["network_interface"]
    }
}
conf = en.CBMConf().from_dictionnary(provider_conf)
provider = en.CBM(conf)
roles, networks = provider.init()
providers.append(provider)
roles = en.sync_info(roles, networks)
floating_ip = roles["server"][0].extra['gateway']

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
    }
}
conf = en.ChameleonEdgeConf.from_dictionnary(provider_conf)
provider = en.ChameleonEdge(conf)
roles_edge, networks_edge = provider.init()
providers.append(provider)


# Merging Chameleon Cloud and Edge resources
for role, hosts in roles_edge.items():
    roles[role] = hosts
logging.info('*' * 40 + f" roles{type(roles)} = {roles}")
logging.info('*' * 40 + f" networks{type(networks)} = {networks}")


# Experimentation logic starts here
# Chameleon Cloud
dest_dir = "/home/cc"
with en.play_on(roles=roles["server"]) as p:
    p.copy(src="./artifacts_cloud/mosquitto.conf",
           dest=dest_dir)
    p.copy(src="./artifacts_cloud/predict_loop.py",
           dest=dest_dir)
    p.copy(src="./artifacts_cloud/edge_cloud.service",
           dest=dest_dir)
    p.copy(src="./artifacts_cloud/cloud_worker.sh",
           dest=dest_dir)
with en.play_on(roles=roles["server"]) as p:
    p.shell(f"bash {dest_dir}/cloud_worker.sh > {dest_dir}/tests")
# Chameleon Edge
for device in roles["client"]:
    cmd_upload = device.upload('./artifacts_edge/', '/')
    logging.info(f"cmd_upload={cmd_upload}")
for device in roles["client"]:
    dir_content = device.execute(f"bash /edge_worker.sh edge_data 100 {floating_ip}")
    logging.info(f"bash = {dir_content['output']}")


logging.info("Running experiment for 300 secs...")
time.sleep(300)
# How to check execution?
# ssh to the Cloud server using floating_ip: ssh cc@<floating_ip>
# tail -f /home/cc/predict.log
# you may also check mosquitto topic:
# mosquitto_sub -v -h 127.0.0.1 -p 1883 -t 'edge_data'


# Releasing resources from Chameleon Cloud and Edge
logging.info("Releasing resources.")
for p in providers:
    p.destroy()
