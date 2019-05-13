# -*- coding: utf-8 -*-
from collections import defaultdict
from ipaddress import IPv4Address
import hashlib
import itertools
import logging
import os

from netaddr import EUI, mac_unix_expanded

from enoslib.api import run_ansible
from enoslib.host import Host
import enoslib.infra.enos_g5k.configuration as g5kconf
import enoslib.infra.enos_g5k.provider as g5kprovider
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from .constants import PLAYBOOK_PATH
from ..provider import Provider

logger = logging.getLogger(__name__)


def start_virtualmachines(provider_conf,
                          g5k_subnet):
    """Starts virtualmachines on G5K.

    Args:
        provider_conf(Configuration):
            :py:class:`enoslib.infra.enos_vmong5k.configuraton.Configuration`
            This is the abstract description of your overcloud (VMs). Each
            configuration has a its undercloud attributes filled with the
            undercloud machines to use. Round Robin strategy to distribute the
            VMs to the PMs will be used for each configuration. Mac addresses
            will be generated according to the g5k_subnet parameter.
        g5k_subnet(dict): The subnet to use. Serialization of
            :py:class:`enoslib.infra.enos_vmong5k.configuraton.NetworkConfiguration`

    Returns:
        (roles, networks) tuple

    """
    def _to_hosts(roles):
        _roles = {}
        for role, machines in roles.items():
            _roles[role] = [m.to_host() for m in machines]
        return _roles

    extra = {}
    if provider_conf.gateway:
        extra.update(gateway=provider_conf.gateway)
    if provider_conf.gateway_user:
        extra.update(gateway_user=provider_conf.gateway_user)

    vmong5k_roles = _distribute(provider_conf.machines,
                                g5k_subnet,
                                extra=extra)

    _start_virtualmachines(provider_conf,
                           vmong5k_roles)

    return _to_hosts(vmong5k_roles), [g5k_subnet]


def _get_subnet_ip(mac):
    # This is the format allowed on G5K for subnets
    address = ['10'] + [str(int(i, 2)) for i in mac.bits().split('-')[-3:]]
    return IPv4Address('.'.join(address))


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
    processors = attributes.architecture['nb_procs']
    cores = attributes.architecture['nb_cores']

    # number of cores as reported in the Website
    return cores * processors


def _find_nodes_number(machine):
    cores = _get_host_cores(machine.cluster)
    return - ((-1 * machine.number * machine.flavour_desc["core"]) // cores)


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
                                          type=vmong5k_conf.subnet_type,
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
                             nodes=_find_nodes_number(machine),
                             primary_network=prod_network)
    return g5k_conf


def _build_g5k_conf(vmong5k_conf):
    """Build the conf of the g5k provider from the vmong5k conf."""
    clusters = [m.cluster for m in vmong5k_conf.machines]
    sites = g5k_api_utils.get_clusters_sites(clusters)
    site_names = set(sites.values())
    if len(site_names) > 1:
        raise Exception("Multisite deployment not supported yet")
    site = site_names.pop()
    return _do_build_g5k_conf(vmong5k_conf, site)


def _build_static_hash(roles, cookie):
    md5 = hashlib.md5()
    _roles = [r for r in roles if r != cookie]
    for r in _roles:
        md5.update(r.encode())
    return md5.hexdigest()


def _distribute(machines, g5k_subnets, extra=None):
    vmong5k_roles = defaultdict(list)
    euis = _mac_range(g5k_subnets)
    static_hashes = {}
    for machine in machines:
        pms = machine.undercloud
        pms_it = itertools.cycle(pms)
        for idx in range(machine.number):
            static_hash = _build_static_hash(machine.roles, machine.cookie)
            static_hashes.setdefault(static_hash, 0)
            static_hashes[static_hash] = static_hashes[static_hash] + 1
            name = "vm-{}-{}-{}".format(
                static_hash,
                static_hashes[static_hash],
                idx)
            pm = next(pms_it)
            vm = VirtualMachine(name,
                                next(euis),
                                machine.flavour_desc,
                                pm,
                                extra=extra)

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


def _start_virtualmachines(provider_conf, vmong5k_roles):
    vms_by_host = _index_by_host(vmong5k_roles)

    extra_vars = {"vms": vms_by_host,
                  "base_image": provider_conf.image,
                  # push the g5k user in the env
                  "g5k_user": os.environ.get("USER"),
                  "working_dir": provider_conf.working_dir,
                  "strategy": provider_conf.strategy,
                  "enable_taktuk": provider_conf.enable_taktuk
                  }
    # pm_inventory_path = os.path.join(os.getcwd(), "pm_hosts")
    # generate_inventory(*g5k_init, pm_inventory_path)
    # deploy virtual machines with ansible playbook
    all_pms = []
    for machine in provider_conf.machines:
        all_pms.extend(machine.undercloud)
    all_pms = {"all": all_pms}

    run_ansible([PLAYBOOK_PATH], roles=all_pms,  extra_vars=extra_vars)


class VirtualMachine(Host):
    """Internal data structure to manipulate virtual machines."""

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
        g5k_subnets = [n for n in g5k_networks if "__subnet__" in n["roles"]]

        # we concretize the virtualmachines
        for machine in self.provider_conf.machines:
            pms = g5k_roles[machine.cookie]
            machine.undercloud = pms

        roles, networks = start_virtualmachines(self.provider_conf,
                                                g5k_subnets)
        return roles, networks

    def destroy(self):
        pass

    def __str__(self):
        return 'VMonG5k'
