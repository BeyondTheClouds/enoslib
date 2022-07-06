from pathlib import Path

import enoslib as en


_ = en.init_logging()

job_name = Path(__file__).name

# claim the resources
conf = (
    en.VMonG5kConf.from_settings(job_name=job_name)
    .add_machine(
        roles=["vms"],
        cluster="paravance",
        number=5,
        flavour_desc={"core": 1, "mem": 1024},
    )
    .finalize()
)

provider = en.VMonG5k(conf)

roles, networks = provider.init()
print(roles)
print(networks)

en.wait_for(roles)

# get the job
job = provider.g5k_provider.jobs[0]

# get the ips to white list
ips = [vm.address for vm in roles["vms"]]

# add ips to the white list for the job duration
en.g5k_api_utils.enable_home_for_job(job, ips)

# mount the home dir
username = en.g5k_api_utils.get_api_username()
with en.actions(roles=roles) as a:
    a.mount(
        src=f"nfs:/export/home/{username}",
        path=f"/home/{username}",
        fstype="nfs",
        state="mounted",
    )
