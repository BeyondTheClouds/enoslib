# -*- coding: utf-8 -*-
from collections import defaultdict
from ipaddress import IPv4Address
import hashlib
import itertools
import logging
import os
from copy import deepcopy

from netaddr import EUI, mac_unix_expanded

import distem as d

from enoslib.api import run_ansible, play_on
from enoslib.host import Host
import enoslib.infra.enos_g5k.configuration as g5kconf
import enoslib.infra.enos_g5k.provider as g5kprovider
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from .constants import (COORDINATOR_ROLE,
                        FILE_DISTEMD_LOGS,
                        PATH_DISTEMD_LOGS,
                        PLAYBOOK_PATH,
                        PROVIDER_PATH)
from ..provider import Provider

logger = logging.getLogger(__name__)


def start_containers(provider_conf, g5k_subnets):
    """Starts containers on G5K.

    Args:
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

    def _to_hosts(roles):
        _roles = {}
        for role, machines in roles.items():
            _roles[role] = [m.to_host() for m in machines]
        return _roles

    '''
    extra = {}
    if provider_conf.gateway:
        extra.update(gateway=provider_conf.gateway)
    if provider_conf.gateway_user:
        extra.update(gateway_user=provider_conf.gateway_user)

    for machine in provider_conf.machines:
        machine.number # Nb de machine dans l'ordre du test
        machine.undercloud # Host avec adresse, dans l'ordre
        machine_roles : ['compute', '630d4b1d27e041cb966d9f417faf30e0']
        machine_flavour_desc : {'core': 1, 'mem': 512}
        machine_cluster : parapide

    distem_roles : {'compute': [Host(container-compute-0, address=10.158.4.2)],
        '77683856df864ecc8b4b5793b7b6de6d':
        [Host(container-compute-0, address=10.158.4.2)],
        'controller': [Host(container-controller-0, address=10.158.4.3),
        Host(container-controller-1,address=10.158.4.4),
        Host(container-controller-2, address=10.158.4.5),
        Host(container-controller-3, address=10.158.4.6),
        Host(container-controller-4, address=10.158.4.7)],
        'ae6a4846338147dd971e02400821f49d':
        [Host(container-controller-0, address=10.158.4.3),
        Host(container-controller-1, address=10.158.4.4),
        Host(container-controller-2, address=10.158.4.5),
        Host(container-controller-3, address=10.158.4.6),
        Host(container-controller-4, address=10.158.4.7)]}


    distemong5k_roles = _distribute(provider_conf.machines, g5k_subnets)
    '''
    
    # Voir pour l'emplacement de l'image
    # Voir pour les clefs - Créer de nouvelles ?
    # Voir pour la valeur de retour de start_containers
    # Non utilisation de _distribute (voir pour répartir tous les vnodes

    _start_containers(provider_conf)

    return _to_hosts(distemong5k_roles), g5k_subnets


def _get_subnet_ip(mac):
    # This is the format allowed on G5K for subnets
    address = ["10"] + [str(int(i, 2)) for i in mac.bits().split("-")[-3:]]
    return IPv4Address(".".join(address))


def _mac_range(g5k_subnets, step=1):
    for g5k_subnet in g5k_subnets:
        start = EUI(g5k_subnet["mac_start"])
        stop = EUI(g5k_subnet["mac_end"])
        for item in range(int(start) + 1, int(stop), step):
            yield EUI(item, dialect=mac_unix_expanded)
    raise StopIteration


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


'''
def _distribute(machines, g5k_subnets, extra=None):
    distemong5k_roles = defaultdict(list)
    euis = _mac_range(g5k_subnets)
    for machine in machines:
        pms = machine.undercloud
        pms_it = itertools.cycle(pms)
        roles_name = machine.roles[0]
        for idx in range(machine.number):
            name = "container-{}-{}".format(roles_name, idx)
            pm = next(pms_it)
            cont = Container(name, next(euis), machine.flavour_desc, pm, extra=extra)

            for role in machine.roles:
                distemong5k_roles[role].append(cont)
    return dict(distemong5k_roles)
'''


def _start_containers(provider_conf):

    distem = Pip_Distem
    FSIMG = "file:///home/rolivo/distem_img/distem-fs-jessie.tar.gz"
    PRIV_KEY = os.path.join(os.environ["HOME"], ".ssh", "id_rsa")
    PUB_KEY = "%s.pub" % PRIV_KEY

    private_key = open(os.path.expanduser(PRIV_KEY)).read()
    public_key = open(os.path.expanduser(PUB_KEY)).read()

    sshkeys = {
        "public" : public_key,
        "private" : private_key
    }
    nodelist = []

    for machine in provider_conf.machines:
        pm = machine.undercloud[0]
        roles_name = machine.roles[0]
        nb = 0
        for idx in range(machine.number):
            name = "node-%s-%s"%(roles_name, idx)
            nodelist.append(name)
            create = distem.vnode_create(name,
                        {'host': pm.address}, sshkeys)
            fs = distem.vfilesystem_create(name,
                                {'image': FSIMG})
    sta = distem.vnodes_start(nodelist)
    

def find_address(roles):
    provider_names=set([])
    for pnodes in roles:
        hosts = roles[pnodes]
        for host in hosts:
            provider_names.add(host.address)
    return provider_names


def write_file_providers(provider_names):
    with open('provider_names', "w"):
            for provid in provider_names:
                with open('provider_names', "a") as f:
                    f.write(provid + "\n")


def _get_controller(roles):
    roles_address=[]
    for _, machines in roles.items():
        for machine in machines:
            roles_address.append(machine)
    return(sorted(roles_address, key=lambda n: n.address)[0])


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

        distem_bootstrap(g5k_roles)
        roles, networks = start_containers(self.provider_conf, g5k_subnets)

    def destroy(self):
        pass

    def __str__(self):
        return "DISTEMonG5k"
