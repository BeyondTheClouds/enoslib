from enoslib import run_command
from enoslib.api import sync_info
from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.infra.enos_iotlab.configuration import Configuration

import logging
import sys
import json

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


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

conf = Configuration.from_dictionary(provider_conf)

p = Iotlab(conf)
try:
    roles, networks = p.init()
    roles = sync_info(roles, networks)
    print(roles)
    print("A8 nodes have a simple linux OS. We can run 'date' command in them.")
    result = run_command(command="date", pattern_hosts="my_a8*", roles=roles)
    print("Results:")
    json.dump(result["ok"], sys.stdout, indent=2)
    json.dump(result["error"], sys.stderr, indent=2)

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
