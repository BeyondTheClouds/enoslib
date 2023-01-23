import logging
import threading
import time

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

stop_reading = False


def reading_thread(serial):
    """
    Reading thread. Continuously read the serial from node.

    Necessary since the getting started tutorial supposes a user interaction
    to send and receive packets at the same time.
    """
    while not stop_reading:
        print(serial.read())


# IoT-LAB provider configuration
provider_conf = {
    "walltime": "01:00",
    "resources": {
        "machines": [
            {
                "roles": ["sensor", "sender"],
                "archi": "m3:at86rf231",
                "site": "grenoble",
                "number": 1,
                "image": "tutorial_m3.elf",
            },
            {
                "roles": ["sensor", "receiver"],
                "archi": "m3:at86rf231",
                "site": "grenoble",
                "number": 1,
                "image": "tutorial_m3.elf",
            },
        ]
    },
}

conf = en.IotlabConf.from_dictionary(provider_conf)

p = en.Iotlab(conf)
try:
    roles, networks = p.init()
    print(roles)

    sender = roles["sender"][0]
    receiver = roles["receiver"][0]
    with en.IotlabSerial(sender, interactive=True) as s_sender, en.IotlabSerial(
        receiver, interactive=True
    ) as s_receiver:

        # Initializing read thread
        print("Initializing reading thread")
        read_thread = threading.Thread(target=reading_thread, args=(s_receiver,))
        read_thread.start()
        time.sleep(1)

        # Sending packets
        print("Sensor (%s) sending small packet" % sender.address)
        s_sender.write("s")
        time.sleep(1)
        print("Sensor (%s) sending big packet" % sender.address)
        s_sender.write("b")
        time.sleep(1)

        stop_reading = True
        read_thread.join()

except Exception as e:
    print(e)
finally:
    # Delete testbed reservation
    p.destroy()
