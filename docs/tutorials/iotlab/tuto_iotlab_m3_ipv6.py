from enoslib import *

import logging
import sys
import time
import re

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

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
import iotlabcli.auth
iotlab_user, _ = iotlabcli.auth.get_user_credentials()

frontend_conf = (
    StaticConf()
    .add_machine(
        roles=["frontend"],
        address="grenoble.iot-lab.info",
        alias="grenoble",
        user=iotlab_user,
    )
    .finalize()
)

conf = IotlabConf.from_dictionary(provider_conf)

p = Iotlab(conf)
f_p = Static(frontend_conf)

try:
    roles, networks = p.init()
    f_roles, f_networks = f_p.init()
    
    print("Iotlab provider: M3 resources")
    print(roles)
    
    print("Static provider: grenoble frontend")
    print(f_roles)
    
    border = roles["border_router"][0]
    frontend = f_roles["frontend"][0]
    
    tun_cmd = "sudo tunslip6.py -v2 -L -a %s -p 20000 2001:660:5307:3100::1/64 > tunslip.output 2>&1" % border.alias
    
    print("Running %s command on frontend: %s" % (tun_cmd, frontend.alias))
    run_command(tun_cmd, roles=f_roles, asynch=3600, poll=0)
    
    # resetting border router
    border.reset()
    
    # getting server addr from tunslip output saved in file
    result = run_command("cat tunslip.output", roles=f_roles)
    out = result['ok']['grenoble']['stdout']
    match = re.search(r'Server IPv6 addresses:\n.+(2001:660:5307:3100::\w{4})', out, re.MULTILINE|re.DOTALL)
    server_addr = match.groups()[0]
    print("Get the Border Router IPv6 address from tunslip output: %s" % server_addr)
    
    # ping
    print("Ping6 BR node using global address:")
    result = run_command('ping6 -c3 %s' % server_addr, roles=f_roles)
    print(result['ok']['grenoble']['stdout'])
    
    # get list of nodes from web interface
    print("View BR’s web-interface: ")
    result = run_command('lynx --dump http://[%s]' % server_addr, roles=f_roles)
    print(result['ok']['grenoble']['stdout'])
    
    print("Stopping tunslip process")
    run_command('pgrep -u "$(whoami)" tunslip6 | xargs kill', roles=f_roles)

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
