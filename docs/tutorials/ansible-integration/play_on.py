from enoslib.api import play_on
from enoslib.infra.enos_vagrant.provider import Enos_vagrant
from enoslib.infra.enos_vagrant.configuration import Configuration

import logging


logging.basicConfig(level=logging.DEBUG)

conf = Configuration.from_settings(backend="libvirt",
                                   box="generic/debian9")\
                    .add_machine(roles=["control"],
                                 flavour="tiny",
                                 number=1)\
                    .add_machine(roles=["compute"],
                                 flavour="tiny",
                                 number=1)\
                    .add_network(roles=["mynetwork"],
                                 cidr="192.168.42.0/24")

provider = Enos_vagrant(conf)
roles, networks = provider.init()
with play_on("all", roles=roles) as p:
    p.apt(name=["apt-transport-https", "ca-certificates", "curl"])
    p.shell(" which docker || (curl -sSL https://get.docker.com/ | sh)")
    p.apt(name="python-pip", state="present")
    p.pip(name="docker", state="present")
    p.docker_container(name="myredis",
                       image="redis",
                       state="started",
                       exposed_ports=[6379],
                       ports=["6379:6379"])
