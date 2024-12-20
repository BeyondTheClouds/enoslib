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
                "number": 2,
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
                "radio": {
                    "mode": "rssi",
                    "num_per_channel": 1,
                    "period": 1,
                    "channels": [11, 14],
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

    print("Opening serial connection to sensor")
    sender = roles["sensor"][0]

    with en.IotlabSerial(sender, interactive=True) as serial_sender:
        num_packets = 5
        num_burst = 5
        print(
            "M3 sensor(%s): sending %d sets of %d packets"
            % (sender.alias, num_burst, num_packets)
        )
        for i in range(0, num_burst):
            for j in range(0, num_packets):
                serial_sender.write("b")
            time.sleep(5)

    print("Collecting experiment data")
    time.sleep(20)
    p.collect_data_experiment()  # collect experiment data

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
