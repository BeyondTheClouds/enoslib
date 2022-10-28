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
                "roles": ["my_rpi"],
                "archi": "rpi3:at86rf233",
                "site": "grenoble",
                "number": 2,
            }
        ]
    },
}

conf = en.IotlabConf.from_dictionary(provider_conf)

p = en.Iotlab(conf)
roles, networks = p.init()
roles = en.sync_info(roles, networks)
print(roles)
print("RPis nodes have a simple linux OS. We can run 'date' command in them.")
result = en.run_command(command="date", roles=roles)
print("Results:")
json.dump(result.to_dict(), sys.stdout, indent=2)
