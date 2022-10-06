import time
from ipaddress import IPv6Network

import enoslib as en


# IoT-LAB provider configuration
iotlab_dict = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["a8"],
                "archi": "a8:at86rf231",
                "site": "grenoble",
                "number": 2,
            }
        ]
    },
}
iotlab_conf = en.IotlabConf.from_dictionary(iotlab_dict)
iotlab_provider = en.Iotlab(iotlab_conf)

g5k_dict = {
    "job_type": [],
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
g5k_conf = en.G5kConf.from_dictionary(g5k_dict)
g5k_provider = en.G5k(g5k_conf)


try:
    iotlab_roles, iotlab_networks = iotlab_provider.init()
    g5k_roles, g5k_networks = g5k_provider.init()

    print("Enabling IPv6 on Grid'5000 nodes")
    en.run_command("dhclient -6 br0", roles=g5k_roles)

    g5k_roles = en.sync_info(g5k_roles, g5k_networks)
    iotlab_roles = en.sync_info(iotlab_roles, iotlab_networks)

    print("Deploy monitoring stack on Grid'5000")
    print("Install Grafana and Prometheus at: %s" % str(g5k_roles["control"]))
    print("Install Telegraf at: %s" % str(g5k_roles["compute"]))

    def get_nets(networks, net_type):
        """Aux method to filter networs from roles"""
        return [
            n
            for net_list in networks.values()
            for n in net_list
            if isinstance(n.network, net_type)
        ]

    m = en.TPGMonitoring(
        collector=g5k_roles["control"][0],
        agent=g5k_roles["compute"] + iotlab_roles["a8"],
        ui=g5k_roles["control"][0],
        networks=get_nets(g5k_networks, IPv6Network)
        + get_nets(iotlab_networks, IPv6Network),
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
