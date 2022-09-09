from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.infra.enos_iotlab.configuration import Configuration
from enoslib.infra.enos_iotlab.objects import IotlabSerial, IotlabSniffer

import logging
import sys
import time
import contextlib

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

provider_conf = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["sniffer"],
                "hostname": ["m3-7.grenoble.iot-lab.info"],
                "image": "tutorial_m3.elf",
                "profile": "sniff_11",
            },
            {
                "roles": ["sensor"],
                "hostname": [
                    "m3-8.grenoble.iot-lab.info",
                    "m3-9.grenoble.iot-lab.info",
                    "m3-10.grenoble.iot-lab.info",
                    "m3-11.grenoble.iot-lab.info",
                ],
                "image": "tutorial_m3.elf",
            },
        ]
    },
    "monitoring": {
        "profiles": [
            {
                "name": "sniff_11",
                "archi": "m3",
                "radio": {
                    "mode": "sniffer",
                    "channels": [11],
                },
            }
        ]
    },
}

conf = Configuration.from_dictionary(provider_conf)

p = Iotlab(conf)
try:

    roles, networks = p.init()
    print(roles)

    sniffer = roles["sniffer"][0]
    sensor = roles["sensor"][0]

    with contextlib.ExitStack() as stack:
        stack.enter_context(IotlabSniffer(sniffer))
        s_sniffer = stack.enter_context(IotlabSerial(sniffer, interactive=True))
        s_sensor = stack.enter_context(IotlabSerial(sensor, interactive=True))

        print("Send a small packet with the sniffer (%s)" % sniffer.alias)
        s_sniffer.write("s")
        print("Send a big packet with another node (%s)" % sensor.alias)
        s_sensor.write("b")

    print("Collecting experiment data")
    time.sleep(1)
    p.collect_data_experiment()  # collect experiment data

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
