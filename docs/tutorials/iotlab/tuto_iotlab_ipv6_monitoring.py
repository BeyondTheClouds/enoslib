from enoslib import *

import logging
import sys
import time

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# IoT-LAB provider configuration
iotlab_dict = {
    "walltime": "01:00",
    "resources":
    {"machines": [
        {
            "roles": ["a8"],
            "archi": "a8:at86rf231",
            "site": "grenoble",
            "number": 2,
        }
    ]}
}
iotlab_conf = IotlabConf.from_dictionary(iotlab_dict)
iotlab_provider = Iotlab(iotlab_conf)

g5k_dict = {
    "job_type": "allow_classic_ssh",
    "walltime": "01:00:00",
    "resources": {
        "machines": [
            {
                "roles": ["control"],
                "cluster": "parasilo",
                "nodes": 1,
                "primary_network": "default",
            },
            {
                "roles": ["compute"],
                "cluster": "parasilo",
                "nodes": 1,
                "primary_network": "default",
            },
        ],
        "networks": [
            {"id": "default", "type": "prod", "roles": ["prod"], "site": "rennes"}
        ],
    },
}
g5k_conf = G5kConf.from_dictionnary(g5k_dict)
g5k_provider = G5k(g5k_conf)


try:
    iotlab_roles, iotlab_networks = iotlab_provider.init()
    g5k_roles, g5k_networks = g5k_provider.init()

    print("Enabling IPv6 on Grid'5000 nodes")
    run_command("dhclient -6 br0", roles=g5k_roles)

    g5k_roles = sync_network_info(g5k_roles, g5k_networks)
    iotlab_roles = sync_network_info(iotlab_roles, iotlab_networks)


    print("Deploy monitoring stack on Grid'5000")
    print("Install Grafana and Prometheus at: %s" % str(g5k_roles["control"]))
    print("Install Telegraf at: %s" % str(g5k_roles["compute"]))
    m = TPGMonitoring(
            collector=g5k_roles["control"][0],
            agent=g5k_roles["compute"]+iotlab_roles["a8"],
            ui=g5k_roles["control"][0],
            network=("prod", IPVersion.IPV6)
    )
    m.deploy()

    ui_address = g5k_roles["control"][0].address
    print("The UI is available at http://%s:3000" % ui_address)
    print("user=admin, password=admin")

    sleep_time = 60
    print("Sleeping for %d seconds before finishing the test" % sleep_time)
    time.sleep(sleep_time)
    m.backup()
    m.destroy()

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    iotlab_provider.destroy()
    g5k_provider.destroy()
