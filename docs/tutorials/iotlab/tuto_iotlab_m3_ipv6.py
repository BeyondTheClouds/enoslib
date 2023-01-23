import logging
import re

import iotlabcli.auth

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["border_router"],
                "archi": "m3:at86rf231",
                "site": "grenoble",
                "number": 1,
                "image": "border-router.iotlab-m3",
            },
            {
                "roles": ["http_server"],
                "archi": "m3:at86rf231",
                "site": "grenoble",
                "number": 9,
                "image": "http-server.iotlab-m3",
            },
        ]
    },
}

# gets the username for accessing the IoT-LAB platform from ~/.iotlabrc file
# you probably can set it hardcoded

iotlab_user, _ = iotlabcli.auth.get_user_credentials()

conf = en.IotlabConf.from_dictionary(provider_conf)

p = en.Iotlab(conf)

try:
    roles, networks = p.init()

    print("Iotlab provider: M3 resources")
    print(roles)

    frontend = en.Host("grenoble.iot-lab.info", user=iotlab_user)

    border = roles["border_router"][0]

    tun_cmd = (
        "sudo tunslip6.py -v2 -L "
        "-a %s -p 20000 2001:660:5307:3100::1/64 > tunslip.output 2>&1" % border.alias
    )

    print(f"Running {tun_cmd} command on frontend: {frontend.alias}")
    en.run_command(tun_cmd, roles=frontend, asynch=3600, poll=0)

    # resetting border router
    border.reset()

    # getting server addr from tunslip output saved in file
    result = en.run_command("cat tunslip.output", roles=frontend)
    out = result["ok"]["grenoble"]["stdout"]
    match = re.search(
        r"Server IPv6 addresses:\n.+(2001:660:5307:3100::\w{4})",
        out,
        re.MULTILINE | re.DOTALL,
    )
    server_addr = match.groups()[0]
    print("Get the Border Router IPv6 address from tunslip output: %s" % server_addr)

    # ping
    print("Ping6 BR node using global address:")
    result = en.run_command("ping6 -c3 %s" % server_addr, roles=frontend)
    print(result["ok"]["grenoble"]["stdout"])

    # get list of nodes from web interface
    print("View BR’s web-interface: ")
    result = en.run_command("lynx --dump http://[%s]" % server_addr, roles=frontend)
    print(result["ok"]["grenoble"]["stdout"])

    print("Stopping tunslip process")
    en.run_command('pgrep -u "$(whoami)" tunslip6 | xargs kill', roles=frontend)

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
