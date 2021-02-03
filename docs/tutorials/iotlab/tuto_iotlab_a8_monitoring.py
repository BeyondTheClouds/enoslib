from enoslib import *

import logging
import sys
import time

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

def setup_vpn(iotlab_roles, pattern="a8"):
    """ Initialize VPN on A8 nodes"""
    with play_on(
        pattern_hosts=pattern, roles=iotlab_roles
    ) as p:
        # running openvpn client in async mode
        p.shell("cd ~/A8/grid5000_vpn/; openvpn Grid5000_VPN.ovpn", asynch=3600, poll=0)
        # setting Grid'5000 DNS server
        p.shell("echo 'nameserver 172.20.255.254' > /etc/resolv.conf")
    

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
            {"id": "default", "type": "prod", "roles": ["my_network"], "site": "rennes"}
        ],
    },
}
g5k_conf = G5kConf.from_dictionnary(g5k_dict)
g5k_provider = G5k(g5k_conf)


try:
    iotlab_roles, _ = iotlab_provider.init()
    g5k_roles, g5k_networks = g5k_provider.init()
    g5k_roles = sync_network_info(g5k_roles, g5k_networks)

    print("Setting up VPN on A8 nodes to put them in the same network as Grid'5000")
    setup_vpn(iotlab_roles)

    print("Deploy monitoring stack on Grid'5000")
    print("Install Grafana and InfluxDB at: %s" % str(g5k_roles["control"]))
    print("Install Telegraf at: %s" % str(g5k_roles["compute"]))
    m = Monitoring(collector=g5k_roles["control"], agent=g5k_roles["compute"]+iotlab_roles["a8"], ui=g5k_roles["control"])
    m.deploy()

    ui_address = g5k_roles["control"][0].extra["my_network_ip"]
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
