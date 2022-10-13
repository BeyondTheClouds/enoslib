import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.DEBUG)

job_name = Path(__file__).name

conf = en.G5kConf.from_settings(job_type=[], job_name=job_name).add_machine(
    roles=["control"], cluster="parasilo", nodes=1
)

provider = en.G5k(conf)
roles, networks = provider.init()

with en.play_on(roles=roles) as p:
    p.apt(name="nginx", state="present")
    p.wait_for(host="localhost", port=80, state="started")

with en.G5kTunnel(roles["control"][0].address, 80) as (local_address, local_port, _):
    import requests

    response = requests.get(f"http://{local_address}:{local_port}")
    print(response.text)
