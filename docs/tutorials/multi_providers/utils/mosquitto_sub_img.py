import random
import paho.mqtt.client as mqtt
import argparse

parser = argparse.ArgumentParser(description="mosquitto-sub")
parser.add_argument(
    "--topic",
    type=str,
    required=True,
    help="MQTT topic",
)
parser.add_argument(
    "--mqtt_broker",
    type=str,
    required=True,
    help="MQTT server address",
)
args = parser.parse_args()

MQTT_SERVER = args.mqtt_broker
MQTT_PATH = args.topic


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(MQTT_PATH)
    # The callback for when a PUBLISH message is received from the server.


def on_message(client, userdata, msg):
    # more callbacks, etc
    # Create a file with write byte permission
    file_name = f"output-{str(random.randint(1, 999))}.jpg"
    f = open(file_name, "wb")
    f.write(msg.payload)
    print(f"Image Received: {file_name}")
    f.close()


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_SERVER, 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
