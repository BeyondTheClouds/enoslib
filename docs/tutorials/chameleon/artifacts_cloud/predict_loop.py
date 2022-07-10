import torchvision
import torch
from PIL import Image
from torchvision import transforms
import paho.mqtt.client as mqtt
from time import sleep
from threading import Lock
import io
import functools
import logging

logging.basicConfig(filename="/home/cc/predict.log", level=logging.DEBUG)
# The MQTT topic to subscribe to
TOPIC = "edge_data"

# Output classes for the pretrained model
classes = [
    '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A', 'N/A',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'N/A', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'N/A', 'dining table',
    'N/A', 'N/A', 'toilet', 'N/A', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


# Sets up the pretrained ML model
@functools.lru_cache(maxsize=None)
def get_model():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn(pretrained=True)
    return model.eval().to(device)


# Set up and get a MQTT client, which delivers images to the model
def get_client():
    def on_connect(client, *args):
        logging.info(f"Subscribing to '{TOPIC}' ...")
        client.subscribe(TOPIC)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.connect("127.0.0.1")

    # Add a bit of delay before attempting to read a first message;
    # there are surely more robust ways of doing this!
    sleep(1)
    
    def on_message(client, userdata, msg):
        logging.info("received image")
        predict(msg.payload)
            
    client.on_message = on_message
    return client


# Evaluate the model on the given input image
def predict(image):
    model = get_model()
    img = Image.open(io.BytesIO(image))
    tensor = transforms.ToTensor()(img).unsqueeze_(0)
    with torch.no_grad():
        predictions = model(tensor)
        write_results([classes[i] for i in predictions[0]['labels'].cpu().numpy()])


# Used to write to the results file in a thread safe way
write_lock = Lock()
def write_results(pred_classes):
    logging.info("getting write lock")
    logging.info(f"pred_classes={pred_classes}")
    with write_lock:
        with open("/home/cc/out.csv", "a") as f:
            # Your output may be stored differently, change as needed
            f.write(",".join(pred_classes)+"\n")


# Iterate over predicts for a given number of times
client = get_client()
while True:
    client.loop()
