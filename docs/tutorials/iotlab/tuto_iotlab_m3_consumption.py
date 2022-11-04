import logging
import time

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

provider_conf = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["sensor"],
                "archi": "m3:at86rf231",
                "site": "grenoble",
                "number": 1,
                "image": "tutorial_m3.elf",
                "profile": "test_profile",
            },
        ]
    },
    "monitoring": {
        "profiles": [
            {
                "name": "test_profile",
                "archi": "m3",
                "consumption": {
                    "current": True,
                    "power": True,
                    "voltage": True,
                    "period": 8244,
                    "average": 4,
                },
            }
        ]
    },
}

conf = en.IotlabConf.from_dictionary(provider_conf)

p = en.Iotlab(conf)
try:

    roles, networks = p.init()
    print(roles)

    print("Running experiment for 60s")
    time.sleep(60)

    print("Collecting experiment data")
    p.collect_data_experiment()  # collect experiment data

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
