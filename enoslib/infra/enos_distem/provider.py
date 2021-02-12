# -*- coding: utf-8 -*-
from collections import defaultdict
from typing import List
from enoslib.infra.enos_distem.configuration import Configuration
import itertools
import logging
import os

import distem as d
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend

from enoslib.api import play_on
from enoslib.objects import Host, Network, Roles
import enoslib.infra.enos_g5k.configuration as g5kconf
from enoslib.infra.enos_g5k.constants import SLASH_22
import enoslib.infra.enos_g5k.provider as g5kprovider
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from .constants import SUBNET_NAME, PATH_DISTEMD_LOGS
from ..provider import Provider


logger = logging.getLogger(__name__)


def start_containers(
    g5k_roles: Roles, provider_conf: Configuration, g5k_subnets: List[Network]
):
    """Starts containers on G5K.

    Args:
        g5k_roles: physical machines to start the containers on.
        provider_conf(Configuration):
            :py:class:`enoslib.infra.enos_distem.configuraton.Configuration`
            This is the abstract description of your overcloud (containers). Each
            configuration has a its undercloud attributes filled with the
            undercloud machines to use. Round Robin strategy to distribute the
            containers to the PMs will be used for each configuration. Mac addresses
            will be generated according to the g5k_subnet parameter.
        g5k_subnets(list): The subnets to use. Each element is a serialization
            of
            :py:class:`enoslib.infra.enos_distem.configuraton.NetworkConfiguration`

    Returns:
        (roles, networks) tuple

    """
    current_dir = os.path.join(os.getcwd(), "keys")
    os.makedirs("%s" % current_dir, exist_ok=True)
    public, private = write_ssh_keys(current_dir)

    keys_path = {"public": public, "private": private}

    distem = distem_bootstrap(g5k_roles, keys_path)

    # For now we only consider a single subnet
    distem_roles = _start_containers(provider_conf, g5k_subnets[0], distem, keys_path)

    return distem_roles, dict(__subnet__=g5k_subnets)


def _get_host_cores(cluster):
    nodes = g5k_api_utils.get_nodes(cluster)
    attributes = nodes[-1]
    processors = attributes.architecture["nb_procs"]
    cores = attributes.architecture["nb_cores"]

    # number of cores as reported in the Website
    return cores * processors


def _find_nodes_number(machine):
    cores = _get_host_cores(machine.cluster)
    return -((-1 * machine.number * machine.flavour_desc["core"]) // cores)


def _do_build_g5k_conf(distemong5k_conf, site):
    g5k_conf = g5kconf.Configuration.from_settings(
        job_name=distemong5k_conf.job_name,
        walltime=distemong5k_conf.walltime,
        queue=distemong5k_conf.queue,
        job_type="deploy",
        force_deploy=distemong5k_conf.force_deploy,
        env_name="debian10-x64-nfs",
    )
    prod_network = g5kconf.NetworkConfiguration(
        roles=["prod"], id="prod", type="prod", site=site
    )
    subnet_roles = distemong5k_conf.networks
    subnet_roles.append("__subnet__")
    subnet = g5kconf.NetworkConfiguration(
        roles=subnet_roles, id="subnet", type=SLASH_22, site=site
    )
    # let's start by adding the networks
    g5k_conf.add_network_conf(prod_network).add_network_conf(subnet)

    for _, machine in enumerate(distemong5k_conf.machines):
        # we hide a descriptor of group in the original machines
        roles = machine.roles
        roles.append(machine.cookie)
        g5k_conf.add_machine(
            roles=roles,
            cluster=machine.cluster,
            nodes=_find_nodes_number(machine),
            primary_network=prod_network,
        )
    return g5k_conf


def _build_g5k_conf(distemong5k_conf):
    """Build the conf of the g5k provider from the vmong5k conf."""
    clusters = [m.cluster for m in distemong5k_conf.machines]
    sites = g5k_api_utils.get_clusters_sites(clusters)
    site_names = set(sites.values())
    if len(site_names) > 1:
        raise Exception("Multisite deployment not supported yet")
    site = site_names.pop()
    return _do_build_g5k_conf(distemong5k_conf, site)


def _start_containers(provider_conf, g5k_subnet, distem, path_sshkeys):
    roles = defaultdict(list)
    FSIMG = provider_conf.image

    sshkeys = {
        "public": open(path_sshkeys["public"]).read(),
        "private": open(path_sshkeys["private"]).read(),
    }

    # handle external access to the containers
    # Currently we need to jump through the coordinator
    # NOTE(msimonin): is there a way in distem to make the vnode reachable from
    # outside directly ? extra = {}
    extra = {"gateway": distem.serveraddr, "gateway_user": "root"}

    distem.vnetwork_create(SUBNET_NAME, g5k_subnet.network.with_prefixlen)
    total = 0
    for machine in provider_conf.machines:
        pms = machine.undercloud
        pms_it = itertools.cycle(pms)
        for idx in range(machine.number):
            pm = next(pms_it)
            name = "vnode-%s" % total
            distem.vnode_create(name, {"host": pm.address}, sshkeys)
            distem.vfilesystem_create(name, {"image": FSIMG})
            network = distem.viface_create(
                name, "if0", {"vnetwork": SUBNET_NAME, "default": "true"}
            )
            distem.vnode_start(name)
            for role in machine.roles:
                # We have to remove the cidr suffix ...
                roles[role].append(
                    Host(
                        network["address"].split("/")[0],
                        user="root",
                        keyfile=path_sshkeys["private"],
                        extra=extra,
                    )
                )
            total = total + 1

    return dict(roles)


def _get_all_hosts(roles):
    all_hosts = set([])
    for _, machines in roles.items():
        for machine in machines:
            all_hosts.add(machine.address)
    return sorted(all_hosts, key=lambda n: n)


def write_ssh_keys(path):
    # Write ssh keys in path directory and return public and private paths
    key = rsa.generate_private_key(
        backend=crypto_default_backend(), public_exponent=65537, key_size=2048
    )
    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption(),
    ).decode("utf-8")
    public_key = (
        key.public_key()
        .public_bytes(
            crypto_serialization.Encoding.OpenSSH,
            crypto_serialization.PublicFormat.OpenSSH,
        )
        .decode("utf-8")
    )

    pub_path = os.path.join(path, "id_rsa.pub")
    priv_path = os.path.join(path, "id_rsa")

    with open(pub_path, "w") as pub:
        pub.write(public_key)
    with open(priv_path, "w") as priv:
        priv.write(private_key)

    os.chmod(pub_path, 0o600)
    os.chmod(priv_path, 0o600)

    return (os.path.join(path, "id_rsa.pub"), os.path.join(path, "id_rsa"))


def distem_bootstrap(roles, path_sshkeys):
    """Bootstrap distem on G5k nodes


    Args :
        roles (dict): physical machines to start containers on.
        path_sshkeys (dict): ssh keys paths

    Return :
        distem (class): distem client
    """

    coordinator = _get_all_hosts(roles)[0]
    distem = d.Distem(serveraddr=coordinator)
    got_pnodes = False

    # check if a client is already running
    try:
        got_pnodes = distem.pnodes_info()
    except Exception:
        logger.error("No pnodes detected - Not critical error")

    with play_on(roles=roles) as p:
        # copy ssh keys for each node
        p.copy(dest="/root/.ssh/id_rsa", src=path_sshkeys["private"], mode="600")
        p.copy(dest="/root/.ssh/id_rsa.pub", src=path_sshkeys["public"], mode="600")
        p.lineinfile(
            path="/root/.ssh/authorized_keys", line=open(path_sshkeys["public"]).read()
        )

        repo = (
            "deb [allow_insecure=yes] http://packages.grid5000.fr/deb/distem/buster/ ./"
        )
        # instal Distem from the debian package
        p.apt_repository(repo=repo, update_cache="no", state="present")
        p.shell("apt-get update")
        p.apt(
            name="distem",
            state="present",
            allow_unauthenticated="yes",
            force="yes",
            force_apt_get="yes",
        )
        # see below
        p.apt(name="tmux", state="present")
        p.apt_repository(repo=repo, update_cache="no", state="absent")

    if got_pnodes:
        distem.pnodes_quit()

    with play_on(roles=roles) as p:
        # kill distem process for each node
        kill_cmd = []
        kill_cmd.append('kill -9 `ps aux|grep "distemd"')
        kill_cmd.append("grep -v grep")
        kill_cmd.append('sed "s/ \\{1,\\}/ /g"')
        kill_cmd.append('cut -f 2 -d" "`')
        p.shell("|".join(kill_cmd) + "|| true")
        p.wait_for(state="stopped", port=4567)
        p.wait_for(state="stopped", port=4568)

    with play_on(pattern_hosts=coordinator, roles=roles) as p:
        p.file(state="directory", dest=PATH_DISTEMD_LOGS)
        # nohup starts distem but 4568 is unreachable (and init-pnodes returns
        # nil) The only thing I found is to start distem in a tmux session...
        # this is weird because distem-bootstrap seems to start correctly
        # distem over SSH without any trouble
        p.shell('tmux new-session -d "exec distemd --verbose -d"')
        p.wait_for(state="started", port=4567, timeout=10)
        p.wait_for(state="started", port=4568, timeout=10)

    distem.pnode_init(_get_all_hosts(roles))

    return distem


class Distem(Provider):
    """Use Distem on G5k"""

    def init(self, force_deploy=False):
        g5k_conf = _build_g5k_conf(self.provider_conf)
        g5k_provider = g5kprovider.G5k(g5k_conf)
        g5k_roles, g5k_networks = g5k_provider.init()
        g5k_subnets = g5k_networks["__subnet__"]

        # we concretize the virtualmachines
        for machine in self.provider_conf.machines:
            pms = g5k_roles[machine.cookie]
            machine.undercloud = pms

        roles, networks = start_containers(g5k_roles, self.provider_conf, g5k_subnets)
        return roles, networks

    def destroy(self):
        pass

    def __str__(self):
        return "DISTEMonG5k"
