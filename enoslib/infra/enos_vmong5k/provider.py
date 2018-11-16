# -*- coding: utf-8 -*-
from .constants import PLAYBOOK_PATH
from ..provider import Provider


from enoslib.api import generate_inventory, run_ansible
from enoslib.host import Host
import enoslib.infra.enos_g5k.api as enoslib
import enoslib.infra.enos_g5k.configuration as g5kconf
import enoslib.infra.enos_g5k.provider as g5kprovider


from collections import defaultdict
import execo_g5k.api_utils as utils
from ipaddress import IPv4Address
import itertools
import logging
from netaddr import EUI, mac_unix_expanded
import os


logger = logging.getLogger(__name__)


def _get_clusters_site(clusters):
    sites = enoslib.get_clusters_sites(clusters)
    site_names = set(sites.values())
    if len(site_names) > 1:
        raise Exception("Multi-site deployment is not supported yet")

    return site_names.pop()


def get_subnet_ip(mac):
    # This is the format allowed on G5K for subnets
    address = ['10'] + [str(int(i, 2)) for i in mac.bits().split('-')[-3:]]
    return IPv4Address('.'.join(address))


def mac_range(start, stop, step=1):
    for item in range(int(start) + 1, int(stop), step):
        yield EUI(item, dialect=mac_unix_expanded)


def get_host_cores(cluster):
    hosts = utils.get_cluster_hosts(cluster)
    # (suppose) all hosts are the same in a cluster
    attributes = utils.get_host_attributes(hosts[-1])
    processors = attributes['architecture']['nb_procs']
    cores = attributes['architecture']['nb_cores']

    # number of cores as reported in the Website
    return cores * processors


def find_nodes_number(machine):
    cores = get_host_cores(machine.cluster)
    return - ((-1 * machine.number * machine.flavour["core"]) // cores)


def _do_build_g5k_conf(vmong5k_conf, site):
    g5k_conf = g5kconf.Configuration.from_settings(
        job_name=vmong5k_conf.job_name,
        walltime=vmong5k_conf.walltime,
        queue=vmong5k_conf.queue,
        job_type="allow_classic_ssh")
    prod_network = g5kconf.NetworkConfiguration(roles=["prod"],
                                           id="prod",
                                           type="prod",
                                           site=site)
    subnet_roles = vmong5k_conf.networks
    subnet_roles.append("__subnet__")
    subnet = g5kconf.NetworkConfiguration(roles=subnet_roles,
                                          id="subnet",
                                          type="slash_22",
                                          site=site)
    # let's start by adding the networks
    g5k_conf.add_network_conf(prod_network)\
           .add_network_conf(subnet)

    for _, machine in enumerate(vmong5k_conf.machines):
        # we hide a descriptor of group in the original machines
        roles = machine.roles
        roles.append(machine.cookie)
        g5k_conf.add_machine(roles=roles,
                            cluster=machine.cluster,
                            nodes=find_nodes_number(machine),
                            primary_network=prod_network)
    return g5k_conf


def _build_g5k_conf(vmong5k_conf):
    """Build the conf of the g5k provider from the vmong5k conf."""
    clusters = [m.cluster for m in vmong5k_conf.machines]
    site = _get_clusters_site(clusters)

    return _do_build_g5k_conf(vmong5k_conf, site)


def _distribute(machines, g5k_roles, g5k_subnet):
    vmong5k_roles = defaultdict(list)
    euis = mac_range(EUI(g5k_subnet["mac_start"]), EUI(g5k_subnet["mac_end"]))
    for machine in machines:
        pms = g5k_roles[machine.cookie]
        pms_it = itertools.cycle(pms)
        for idx in range(machine.number):
            name = "vm-{}".format(idx)
            pm = next(pms_it)
            vm = VirtualMachine(name, next(euis), machine.flavour, pm)

            for role in machine.roles:
                vmong5k_roles[role].append(vm)
    return dict(vmong5k_roles)


def _index_by_host(roles):
    virtual_machines_by_host = defaultdict(set)
    for vms in roles.values():
        for virtual_machine in vms:
            host = virtual_machine.pm
            # Two vms are equal if they have the same euis
            virtual_machines_by_host[host.alias].add(
                virtual_machine)
    # now serialize all the thing
    vms_by_host = defaultdict(list)
    for host, vms in virtual_machines_by_host.items():
        for virtual_machine in vms:
            vms_by_host[host].append(virtual_machine.to_dict())

    return dict(vms_by_host)


def start_virtualmachines(provider_conf, g5k_init, vmong5k_roles):
    vms_by_host = _index_by_host(vmong5k_roles)

    extra_vars = {'vms': vms_by_host,
                  'base_image': provider_conf.image}
    pm_inventory_path = os.path.join(os.getcwd(), "pm_hosts")
    generate_inventory(*g5k_init, pm_inventory_path)
    # deploy virtual machines with ansible playbook
    run_ansible([PLAYBOOK_PATH], pm_inventory_path, extra_vars)


class VirtualMachine(Host):

    def __init__(self, name, eui, flavour, pm):
        super().__init__(str(get_subnet_ip(eui)), alias=name)
        self.core = flavour["core"]
        # libvirt uses kiB by default
        self.mem = int(flavour["mem"]) * 1024
        self.eui = eui
        self.pm = pm

    def to_dict(self):
        d = super().to_dict()
        d.update(core=self.core, mem=self.mem, eui=str(self.eui),
                 pm=self.pm.to_dict())
        return d

    def __hash__(self):
        return int(self.eui)

    def __eq__(self, other):
        return int(self.eui) == int(other.eui)


class VMonG5k(Provider):
    """The provider to use when deploying virtual machines on Grid'5000."""

    def init(self, force_deploy=False):
        g5k_conf = _build_g5k_conf(self.provider_conf)
        g5k_provider = g5kprovider.G5k(g5k_conf)
        g5k_roles, g5k_networks = g5k_provider.init()
        g5k_subnet = [n for n in g5k_networks if "__subnet__" in n["roles"]][0]
        vmong5k_roles = _distribute(self.provider_conf.machines,
                                    g5k_roles,
                                    g5k_subnet)

        start_virtualmachines(self.provider_conf,
                              (g5k_roles, g5k_networks),
                              vmong5k_roles)

        return vmong5k_roles, [g5k_subnet]

    def destroy(self):
        pass

    def __str__(self):
        return 'VMonG5k'
