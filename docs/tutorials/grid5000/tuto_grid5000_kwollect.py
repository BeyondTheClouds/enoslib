import logging
import time
from pathlib import Path
from pprint import pprint

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = (
    en.G5kConf.from_settings(job_name=job_name, walltime="0:20:00")
    .add_machine(roles=["all", "idle"], cluster="ecotype", nodes=1)
    .add_machine(roles=["all", "stress"], cluster="ecotype", nodes=1)
)

# This will validate the configuration, but not reserve resources yet
provider = en.G5k(conf)

# Get actual resources
roles, networks = provider.init()

# Global monitor
monitor = en.Kwollect(nodes=roles["all"])
monitor.deploy()

# Run a loop of stress tests under the monitor
monitor.start()

duration = 20
cores = 4
for run in range(3):
    en.run_command(f"stress -c {cores} -t {duration}", roles=roles["stress"])
    print(f"Sleeping for {duration} seconds")
    time.sleep(duration)

# Run an additional stress test with a nested monitor, using a context manager
with en.Kwollect(nodes=roles["stress"]) as local_monitor:
    en.run_command(f"stress -c {cores} -t {duration}", roles=roles["stress"])
print(f"Sleeping for {duration} seconds")
time.sleep(duration)

# Stop global monitor
monitor.stop()

# Get power metrics from global monitor
metrics = monitor.get_metrics(metrics=["bmc_node_power_watt"])
pprint(metrics)

monitor.backup("./enoslib_tuto_kwollect")
monitor.backup("./enoslib_tuto_kwollect_subset", metrics=["bmc_node_power_watt"])

# Get CPU metrics from nested monitor
metrics = local_monitor.get_metrics(metrics=["prom_node_cpu_scaling_frequency_hertz"])
# Compute average CPU frequency across all cores and time for the stressed machine
datapoints = metrics["nantes"]
average_freq = sum(m["value"] for m in datapoints) / len(datapoints) / 1000000
print(f"Average CPU frequency: {average_freq} MHz")

# Available metrics are listed here:
# https://www.grid5000.fr/w/Monitoring_Using_Kwollect#Metrics_available_in_Grid'5000

# Release all Grid'5000 resources
provider.destroy()
