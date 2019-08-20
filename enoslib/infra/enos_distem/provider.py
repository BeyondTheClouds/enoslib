# -*- coding: utf-8 -*-
from collections import defaultdict
from copy import deepcopy
import hashlib
from ipaddress import IPv4Address
import itertools
import logging
import os

import distem as d
from netaddr import EUI, mac_unix_expanded

from enoslib.api import run_ansible, play_on
from enoslib.host import Host
import enoslib.infra.enos_g5k.configuration as g5kconf
import enoslib.infra.enos_g5k.provider as g5kprovider
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from .constants import (COORDINATOR_ROLE,
                        FILE_DISTEMD_LOGS,
                        PATH_DISTEMD_LOGS,
                        PLAYBOOK_PATH,
                        PROVIDER_PATH,
                        SUBNET_NAME)
from ..provider import Provider


logger = logging.getLogger(__name__)


def start_containers(g5k_roles, provider_conf, g5k_subnets):
    """Starts containers on G5K.

    Args:
        g5k_roles (dict): physical machines to start the containers on.
        provider_conf(Configuration):
            :py:class:`enoslib.infra.enos_distem.configuraton.Configuration`
            This is the abstract description of your overcloud (VMs). Each
            configuration has a its undercloud attributes filled with the
            undercloud machines to use. Round Robin strategy to distribute the
            VMs to the PMs will be used for each configuration. Mac addresses
            will be generated according to the g5k_subnet parameter.
        g5k_subnets(list): The subnets to use. Each element is a serialization
            of
            :py:class:`enoslib.infra.enos_distem.configuraton.NetworkConfiguration`

    Returns:
        (roles, networks) tuple

    """

    # Voir pour l'emplacement de l'image
    # Voir pour les clefs - Créer de nouvelles ?
    # Voir pour la valeur de retour de start_containers
    # Non utilisation de _distribute (voir pour répartir tous les vnodes
    coordinator = distem_bootstrap(g5k_roles)

    # For now we only consider a single subnet
    distem_roles = _start_containers(coordinator, provider_conf, g5k_subnets[0])

    return distem_roles, g5k_subnets


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
        force_deploy=distemong5k_conf.force_deploy
    )
    prod_network = g5kconf.NetworkConfiguration(
        roles=["prod"], id="prod", type="prod", site=site
    )
    subnet_roles = distemong5k_conf.networks
    subnet_roles.append("__subnet__")
    subnet = g5kconf.NetworkConfiguration(
        roles=subnet_roles, id="subnet", type=distemong5k_conf.subnet_type, site=site
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


def _start_containers(coordinator, provider_conf, g5k_subnet):
    roles = defaultdict(list)
    distem = d.Distem()
    import ipdb; ipdb.set_trace()
    # distem = d.Distem(serveraddr=coordinator.address)
    FSIMG = "file:///home/msimonin/public/distem-fs-jessie.tar.gz"
    PRIV_KEY = os.path.join(os.environ["HOME"], ".ssh", "id_rsa")
    PUB_KEY = "%s.pub" % PRIV_KEY

    private_key = open(os.path.expanduser(PRIV_KEY)).read()
    public_key = open(os.path.expanduser(PUB_KEY)).read()

    sshkeys = {
        "public" : public_key,
        "private" : private_key
    }

    # handle external access to the containers
    # Currently we need to jump through the coordinator
    # NOTE(msimonin): is there a way in distem to make the vnode reachable from
    # outside directly ? extra = {}
    extra.update(gateway=coordinator.address)
    extra.update(gateway_user="root")

    distem.vnetwork_create(SUBNET_NAME, g5k_subnet["cidr"])
    total = 0
    for machine in provider_conf.machines:
        pms = machine.undercloud
        pms_it = itertools.cycle(pms)
        roles_name = machine.roles[0]
        for idx in range(machine.number):
            pm = next(pms_it)
            name = "vnode-%s" % total
            create = distem.vnode_create(name,
                        {"host": pm.address}, sshkeys)
            fs = distem.vfilesystem_create(name,
                                {"image": FSIMG})
            network = distem.viface_create(name,
                                           "if0",
                                           {"vnetwork": SUBNET_NAME, "default":  "true"})
            result = distem.vnode_start(name)
            for role in machine.roles:
                # We have to remove the cidr suffix ...
                roles[role].append(Host(network["address"].split("/")[0],
                                   user="root",
                                   keyfile=PRIV_KEY,
                                   extra=extra))
            total = total + 1

    return dict(roles)


def _get_controller(roles):
    all_hosts = []
    for _, machines in roles.items():
        for machine in machines:
            all_hosts.append(machine)
    return(sorted(all_hosts, key=lambda n: n.address)[0])


def distem_bootstrap(roles):
    _user = g5k_api_utils.get_api_username()
    # TODO: generate keys on the fly
    keys_path = os.path.join(PROVIDER_PATH, "keys")
    private = os.path.join(keys_path, "id_rsa")
    public = os.path.join(keys_path, "id_rsa.pub")
    with play_on(roles=roles) as p:
        p.copy(dest="/root/.ssh/id_rsa", src=private)
        p.copy(dest="/root/.ssh/id_rsa.pub", src=public)
        p.lineinfile(path="/root/.ssh/authorized_keys", line=public, regexp=public)

        ## instal Distem from the debian package
        p.apt_repository(repo="deb [allow_insecure=yes] http://distem.gforge.inria.fr/deb-stretch ./",
                         update_cache="no", state="present")
        p.shell("apt-get update")
        p.apt(name="distem",
              state="present",
              allow_unauthenticated="yes",
              force="yes",
              force_apt_get="yes" )
        # see below
        p.apt(name="tmux", state="present")

    coordinator = _get_controller(roles)
    # kill coordinator on any nodes
    with play_on(roles=roles) as p:
        p.shell("kill -9 `ps aux|grep \"distemd\"|grep -v grep|sed \"s/ \{1,\}/ /g\"|cut -f 2 -d\" \"` || true")
        p.wait_for(state="stopped", port=4567)
        p.wait_for(state="stopped", port=4568)

    with play_on(pattern_hosts=coordinator.alias, roles=roles) as p:
        p.file(state="directory", dest=PATH_DISTEMD_LOGS)
        # nohup starts distem but 4568 is unreachable (and init-pnodes returns
        # nil) The only thing I found is to start distem in a tmux session...
        # this is weird because distem-bootstrap seems to start correctly
        # distem over SSH without any trouble
        p.shell("tmux new-session -d \"exec distemd --verbose -d\"")
        p.wait_for(state="started", port=4567, timeout=10)
        p.wait_for(state="started", port=4568, timeout=10)
    with play_on(roles=roles) as p:
        p.shell("distem --coordinator host=%s --init-pnode {{ inventory_hostname }}" %(coordinator.address))

    return coordinator


class Container(Host):
    """Internal data structure to manipulate containers"""

    def __init__(self, name, eui, flavour_desc, pm, extra=None):
        super().__init__(str(_get_subnet_ip(eui)), alias=name, extra=extra)
        self.core = flavour_desc["core"]
        # libvirt uses kiB by default
        self.mem = int(flavour_desc["mem"]) * 1024
        self.eui = eui
        self.pm = pm
        self.user = "root"

    def to_dict(self):
        d = super().to_dict()
        d.update(core=self.core, mem=self.mem, eui=str(self.eui), pm=self.pm.to_dict())
        return d

    def __hash__(self):
        return int(self.eui)

    def __eq__(self, other):
        return int(self.eui) == int(other.eui)


class Distem(Provider):
    """Use Distem on G5k"""

    def init(self, force_deploy=False):
        g5k_conf = _build_g5k_conf(self.provider_conf)
        g5k_provider = g5kprovider.G5k(g5k_conf)
        g5k_roles, g5k_networks = g5k_provider.init()
        g5k_subnets = [n for n in g5k_networks if "__subnet__" in n["roles"]]

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
