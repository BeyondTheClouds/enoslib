import logging
import sys
import json

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# IoT-LAB provider configuration
provider_conf = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["my_a8"],
                "archi": "a8:at86rf231",
                "site": "grenoble",
                "number": 2,
            }
        ]
    },
}

conf = en.IotlabConf.from_dictionary(provider_conf)

p = en.Iotlab(conf)
try:
    roles, networks = p.init()
    roles = en.sync_info(roles, networks)
    print(roles)
    print("A8 nodes have a simple linux OS. We can run 'date' command in them.")
    result = en.run_command(command="date", pattern_hosts="my_a8*", roles=roles)
    print("Results:")
    json.dump(result["ok"], sys.stdout, indent=2)
    json.dump(result["error"], sys.stderr, indent=2)

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
