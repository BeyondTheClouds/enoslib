import json
import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

job_name = Path(__file__).name

conf = en.G5kConf.from_settings(
    job_name=job_name, job_type=[], walltime="0:30:00"
).add_machine(
    roles=["storage"],
    cluster="grimoire",
    nodes=2,
    reservable_disks=True,
)

provider = en.G5k(conf)

# Get actual resources
roles, _ = provider.init()

with en.actions(roles=roles) as p:
    # Check that the expected disks are present.
    # https://www.grid5000.fr/w/Nancy:Hardware#grimoire
    # Notice that we use the "diskN" aliases because they are more
    # stable than "sdX".
    disks = ["disk1", "disk2", "disk3", "disk4"]
    for disk in disks:
        p.command(f"test -e /dev/{disk}", task_name=f"Check availability of {disk}")

    # Partition disks
    for disk in disks:
        p.shell(
            f"echo -e 'label: gpt\n,,raid' | sfdisk --no-reread /dev/{disk}",
            task_name=f"Create partition on {disk}",
        )

    # Create a software RAID-5 array
    nb_disks = len(disks)
    raid_parts = " ".join(f"/dev/{disk}p1" for disk in disks)
    p.shell(
        f"grep -q md0 /proc/mdstat || "
        f"mdadm --create /dev/md0 --run --level 5 "
        f"--raid-devices {nb_disks} {raid_parts}",
        task_name="Create RAID array",
    )

    # Run FIO to benchmark the array (at the block device level)
    p.apt(name="fio", state="present", task_name="Install fio")
    p.command(
        "fio --output-format=json --name=enoslib --ioengine=libaio "
        "--direct=1 --gtod_reduce=1 --readwrite=randread "
        "--bs=4K --iodepth=8 --numjobs=8 --runtime 30s "
        "--filename=/dev/md0",
        task_name="Run fio",
    )

    # Destroy everything
    p.command("mdadm --stop /dev/md0", task_name="Stop RAID array")
    p.command(f"wipefs -a {raid_parts}", task_name="Wipe RAID signatures")

results = p.results

# Get output of FIO and print result
res_per_node = {res.host: res.stdout for res in results.filter(task="Run fio")}
for host, output in res_per_node.items():
    data = json.loads(output)
    # Sum performance of all parallel FIO "jobs"
    read_perf_iops = sum(job["read"]["iops"] for job in data["jobs"])
    print(
        f"{data['fio version']} running on {host}: "
        f"average /dev/md0 read performance = {read_perf_iops:.2f} IOPS"
    )


# Release all Grid'5000 resources
provider.destroy()
