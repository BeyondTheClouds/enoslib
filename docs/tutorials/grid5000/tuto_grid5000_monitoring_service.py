import logging
from pathlib import Path

import enoslib as en

en.init_logging(level=logging.INFO)
en.check()

# More readable to debug issues
en.set_config(ansible_stdout="regular")

job_name = Path(__file__).name

CLUSTER = "paradoxe"

conf = (
    en.G5kConf.from_settings(job_type=[], job_name=job_name, walltime="0:30:00")
    .add_machine(roles=["control"], cluster=CLUSTER, nodes=1)
    .add_machine(roles=["agent"], cluster=CLUSTER, nodes=1)
)

provider = en.G5k(conf)
roles, networks = provider.init()


registry_opts = dict(type="external", ip="docker-cache.grid5000.fr", port=80)

d = en.Docker(
    agent=roles["control"] | roles["agent"],
    bind_var_docker="/tmp/docker",
    registry_opts=registry_opts,
)
d.deploy()

# testing TIG stack
m_tig = en.TIGMonitoring(
    collector=roles["control"][0], agent=roles["agent"], ui=roles["control"][0]
)
m_tig.deploy()
m_tig.backup()
# test whether the backup is ok...
m_tig.destroy()

# testing TPG stack
m_tpg = en.TPGMonitoring(
    collector=roles["control"][0], agent=roles["agent"], ui=roles["control"][0]
)
m_tpg.deploy()
m_tpg.backup()
m_tpg.destroy()


# Release all Grid'5000 resources
provider.destroy()
