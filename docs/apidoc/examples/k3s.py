import enoslib as en

en.init_logging()

# claim the resources
conf = (
    en.G5kConf.from_settings(walltime="0:45:00", job_type=[], job_name="k3s")
    .add_machine(roles=["master"], cluster="paravance", nodes=1)
    .add_machine(roles=["agent"], cluster="paravance", nodes=10)
    .finalize()
)


provider = en.G5k(conf)
# Get actual resources
roles, networks = provider.init()


k3s = en.K3s(master=roles["master"], agent=roles["agent"])
k3s.deploy()
