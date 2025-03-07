#!/usr/bin/env -S uv run

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "enoslib>=10,<11",
#     "pyyaml>=6,<7",
# ]
# ///

"""This script takes an Ansible inventory, provisions the requested hosts
using VMs on Grid'5000, and writes an updated inventory with the correct
connection variables (ansible_host with host IP, SSH config with jump
hosts, etc)

To run this script, we recommend using https://docs.astral.sh/uv/

Example input inventory:
(must be called something like "inventory/00-something.yml"):

```yaml
my_group:
  hosts:
    host01:  # No var, just a host declaration
    host02:
      custom_var: foobar
      other_custom_var: barfoo

```

Generated output inventory at "inventory/99-auto-generated-enoslib.yml":
(Ansible will automatically merge it with the input inventory):

```yaml
my_group:
  hosts:
    host01:
      ansible_host: 10.176.0.2
      ansible_ssh_common_args: -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -J myuser@access.grid5000.fr
      ansible_user: root
    host02:
      ansible_host: 10.176.0.3
      ansible_ssh_common_args: -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -J myuser@access.grid5000.fr
      ansible_user: root
```
"""

import argparse
import datetime
import logging
from pathlib import Path

import yaml

import enoslib as en


def parse_inventory(args):
    with open(args.inventory_file) as src_inventory:
        inventory = yaml.safe_load(src_inventory.read())
    return inventory


def write_inventory(args, src_inventory: dict, hosts):
    src_path = Path(args.inventory_file)
    dst_path = src_path.parent / "99-auto-generated-enoslib.yml"
    # Allocate concrete hosts to original Ansible hosts
    host_mapping = {}
    for group, subconf in src_inventory.items():
        for hostname in subconf["hosts"].keys():
            if hostname not in host_mapping:
                host = hosts.pop()
                host_mapping[hostname] = host
    # print(host_mapping)
    # Update src inventory to add hostnames
    dst_inventory = {}
    for group, subconf in src_inventory.items():
        dst_inventory[group] = dict(hosts={})
        for hostname in subconf["hosts"].keys():
            host = host_mapping[hostname]
            base_ssh_args = (
                "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            )
            ssh_gw = host.extra["gateway"]
            ssh_gw_user = host.extra["gateway_user"]
            dst_inventory[group]["hosts"][hostname] = {
                "ansible_host": host.address,
                "ansible_user": host.user,
                "ansible_ssh_common_args": f"{base_ssh_args} -J {ssh_gw_user}@{ssh_gw}",
            }
    # print(dst_inventory)
    print(f"Writing updated inventory to {dst_path}")
    with open(dst_path, "w") as dst:
        yaml.dump(dst_inventory, dst)


def timedelta_to_walltime(delta: datetime.timedelta):
    duration = delta.total_seconds()
    if duration < 0:
        raise ValueError("Cannot convert negative timedelta to walltime")
    hours = int(duration // 3600)
    minutes = int((duration // 60) % 60)
    seconds = int(duration % 60)
    return f"{hours}:{minutes}:{seconds}"


def provision_g5k(args, src_inventory: dict):
    if args.walltime == "auto":
        now = datetime.datetime.now()
        # Case 1: before 17:00, reserve until 18:55 the same day
        limit1 = datetime.datetime.combine(now.date(), datetime.time(17, 00))
        target1 = datetime.datetime.combine(now.date(), datetime.time(18, 55))
        # Case 2: after 17:00, reserve until 20:55 the same day
        target2 = datetime.datetime.combine(now.date(), datetime.time(20, 55))
        if now < limit1:
            print("Reserving resources until 18:55 today")
            walltime = timedelta_to_walltime(target1 - now)
        else:
            print("Reserving resources until 20:55 today")
            walltime = timedelta_to_walltime(target2 - now)
    else:
        walltime = args.walltime
    g5kconf = en.VMonG5kConf.from_settings(
        job_name="g5k_ansible_vm",
        image=f"/grid5000/virt-images/{args.os}.qcow2",
        walltime=walltime,
    )
    # Collect unique hosts
    target_hosts = set()
    for group, subconf in src_inventory.items():
        target_hosts.update(subconf["hosts"].keys())
    # Ask for all G5K hosts in a single EnOSlib group
    g5kconf.add_machine(
        roles=["ansible"],
        cluster=args.cluster,
        number=len(target_hosts),
        flavour_desc={"core": args.cores, "mem": args.mem},
    )
    provider = en.VMonG5k(g5kconf)
    print("Reserving nodes and deploying VMs, this might take a few minutes...")
    roles, networks = provider.init()
    en.wait_for(roles)
    return roles["ansible"]


def modify_reserved_host(hosts):
    with en.actions(roles=hosts) as a:
        # Fix docker python lib install via pip
        a.file(path="/usr/lib/python3.11/EXTERNALLY-MANAGED", state="absent")


def main() -> int:
    # Cmdline arguments
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "inventory_file",
        help="the source Ansible "
        "inventory file (should be inside an inventory/ directory)",
    )
    parser.add_argument(
        "--cluster",
        default="ecotype",
        help="The Grid'5000 cluster to use as VM host (default: %(default)s)",
    )
    parser.add_argument(
        "--cores",
        "-c",
        default=2,
        type=int,
        help="Number of CPU cores for each VM (default: %(default)s)",
    )
    parser.add_argument(
        "--mem",
        "-m",
        default=4096,
        type=int,
        help="Amount of memory in MB for each VM (default: %(default)s)",
    )
    parser.add_argument(
        "--os",
        default="debian12-x64-min",
        help="OS image to use (default: %(default)s)",
    )
    parser.add_argument(
        "--walltime",
        default="auto",
        help="Duration of VM reservation [HH:MM:SS] "
        "(default: '%(default)s' = rest of the day)",
    )
    args = parser.parse_args()
    # Let's do actual work
    en.init_logging(level=logging.INFO)
    inventory = parse_inventory(args)
    hosts = provision_g5k(args, inventory)
    modify_reserved_host(hosts)
    write_inventory(args, inventory, hosts)
    return 0


if __name__ == "__main__":
    exit(main())
