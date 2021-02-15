# -*- coding: utf-8 -*-
from collections import defaultdict
from enoslib.infra.enos_g5k.objects import G5kEnosSubnetNetwork
from ipaddress import IPv4Address
import itertools
import logging
import operator
from typing import Dict, List

from netaddr import EUI, mac_unix_expanded

from enoslib.api import run_ansible
from enoslib.objects import Host, Network, RolesNetworks
import enoslib.infra.enos_g5k.configuration as g5kconf
import enoslib.infra.enos_g5k.provider as g5kprovider
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from .configuration import Configuration
from .constants import DESTROY_PLAYBOOK_PATH, PLAYBOOK_PATH, LIBVIRT_DIR
from ..provider import Provider

logger = logging.getLogger(__name__)


def start_virtualmachines(
    provider_conf: Configuration,
    g5k_subnets: List[Network],
    skip: int = 0,
    force_deploy: bool = False,
) -> RolesNetworks:
    """Starts virtualmachines on G5K.

    This first distributes the virtual machine according to the undercloud
    attributes of the configuration, assign them IPs and start them.
    It is idempotent.

    Args:
        provider_conf: This is the abstract description of your overcloud (VMs).
            Each configuration must have its undercloud attributes filled with the
            undercloud machines to use. Round Robin strategy to distribute the VMs
            to the PMs will be used for each configuration. Mac addresses will be
            generated according to the g5k_subnet parameter.
        g5k_subnets: The subnets to use. Each element is a serialization
            of
            :py:class:`enoslib.infra.enos_vmong5k.configuraton.NetworkConfiguration`
        skip: number of addresses to skip when distributing them to the virtual
              machines. This can be useful when starting incrementally the
              virtual machines to avoid overlaping ip assignements between iterations.
        force_deploy (boolean): controls whether the virtual machines should be
            restarted from scratch.

    Examples:

        .. literalinclude:: ./examples/grid5000/tuto_grid5000_p_virt.py
            :language: python
            :linenos:

        .. literalinclude:: ./examples/grid5000/tuto_grid5000_p_virt_batch.py
            :language: python
            :linenos:

    Returns:
        (roles, networks) tuple

    """

    extra: Dict = {}
    if provider_conf.gateway:
        extra.update(gateway="access.grid5000.fr")
        extra.update(gateway_user=g5k_api_utils.get_api_username())

    vmong5k_roles = _distribute(
        provider_conf.machines, g5k_subnets, skip=skip, extra=extra
    )

    _start_virtualmachines(provider_conf, vmong5k_roles, force_deploy=force_deploy)

    return vmong5k_roles, dict(__subnet__=g5k_subnets)


def _get_subnet_ip(mac):
    # This is the format allowed on G5K for subnets
    address = ["10"] + [str(int(i, 2)) for i in mac.bits().split("-")[-3:]]
    return IPv4Address(".".join(address))


def _mac_range(g5k_subnets: List[G5kEnosSubnetNetwork], skip=0, step=1):
    # be a bit defensive here by making sure the addresses sequence is
    # outputed deterministically
    to_skip = skip
    _g5k_subnets = sorted(g5k_subnets, key=operator.attrgetter("network"))
    for g5k_subnet in _g5k_subnets:
        it_mac = g5k_subnet.free_macs
        # we always skip the first one as this could not be a regular address
        # e.g 10.158.0.0
        next(it_mac)
        emitted = False
        for mac in itertools.islice(it_mac, to_skip, None, step):
            yield EUI(mac, dialect=mac_unix_expanded)
            emitted = True
        if not emitted:
            to_skip -= len(list(g5k_subnet.free_macs))
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


def _do_build_g5k_conf(vmong5k_conf, site):
    g5k_conf = g5kconf.Configuration.from_settings(
        job_name=vmong5k_conf.job_name,
        walltime=vmong5k_conf.walltime,
        queue=vmong5k_conf.queue,
        job_type="allow_classic_ssh",
    )
    prod_network = g5kconf.NetworkConfiguration(
        roles=["prod"], id="prod", type="prod", site=site
    )
    subnet_roles = vmong5k_conf.networks
    subnet_roles.append("__subnet__")
    subnet = g5kconf.NetworkConfiguration(
        roles=subnet_roles, id="subnet", type=vmong5k_conf.subnet_type, site=site
    )
    # let's start by adding the networks
    g5k_conf.add_network_conf(prod_network).add_network_conf(subnet)

    for _, machine in enumerate(vmong5k_conf.machines):
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


def _build_g5k_conf(vmong5k_conf):
    """Build the conf of the g5k provider from the vmong5k conf."""
    clusters = [m.cluster for m in vmong5k_conf.machines]
    sites = g5k_api_utils.get_clusters_sites(clusters)
    site_names = set(sites.values())
    if len(site_names) > 1:
        raise Exception("Multisite deployment not supported yet")
    site = site_names.pop()
    return _do_build_g5k_conf(vmong5k_conf, site)


def _distribute(machines, g5k_subnets, skip=0, extra=None):
    vmong5k_roles = defaultdict(list)
    euis = _mac_range(g5k_subnets, skip=skip)
    for machine in machines:
        pms = machine.undercloud
        pms_it = itertools.cycle(pms)
        extra_devices = machine.extra_devices
        for _ in range(machine.number):
            eui = next(euis)
            descriptor = "-".join(str(_get_subnet_ip(eui)).split(".")[1:])
            name = f"virtual-{descriptor}"
            pm = next(pms_it)
            vm = VirtualMachine(
                name,
                eui,
                machine.flavour_desc,
                pm,
                extra=extra,
                extra_devices=extra_devices,
            )

            for role in machine.roles:
                vmong5k_roles[role].append(vm)
    return dict(vmong5k_roles)


def _index_by_host(roles):
    virtual_machines_by_host = defaultdict(set)
    pms = set()
    for vms in roles.values():
        for virtual_machine in vms:
            host = virtual_machine.pm
            # Two vms are equal if they have the same euis
            virtual_machines_by_host[host.alias].add(virtual_machine)
            pms.add(host)
    # now serialize all the thing
    vms_by_host = defaultdict(list)
    for host, vms in virtual_machines_by_host.items():
        for virtual_machine in vms:
            # beware the intend here is to get something that is json-serializable
            # passing a set to ansible will basically fail so we take care of this here
            vm_dict = virtual_machine.to_dict()
            vms_by_host[host].append(vm_dict)

    return dict(vms_by_host), pms


def _start_virtualmachines(provider_conf, vmong5k_roles, force_deploy=False):
    vms_by_host, pms = _index_by_host(vmong5k_roles)

    extra_vars = {
        "vms": vms_by_host,
        "base_image": provider_conf.image,
        # push the g5k user in the env
        "g5k_user": g5k_api_utils.get_api_username(),
        "working_dir": provider_conf.working_dir,
        "_strategy": provider_conf.strategy,
        "enable_taktuk": provider_conf.enable_taktuk,
        "libvirt_dir": LIBVIRT_DIR,
    }

    # Take into account only the pms that will host the vms
    # this might happen when #pms > #vms
    all_pms = {"all": pms}

    if force_deploy:
        run_ansible([DESTROY_PLAYBOOK_PATH], roles=all_pms, extra_vars=extra_vars)

    run_ansible([PLAYBOOK_PATH], roles=all_pms, extra_vars=extra_vars)


class VirtualMachine(Host):
    """Internal data structure to manipulate virtual machines."""

    def __init__(self, name, eui, flavour_desc, pm, extra=None, extra_devices=""):
        super().__init__(str(_get_subnet_ip(eui)), alias=name, extra=extra)
        self.core = flavour_desc["core"]
        # libvirt uses kiB by default
        self.mem = int(flavour_desc["mem"]) * 1024
        self.eui = eui
        self.pm = pm
        self.user = "root"
        self.net_devices = extra_devices
        self.disk = flavour_desc.get("disk", None)
        if self.disk is not None:
            path = f"{LIBVIRT_DIR}/{self.alias}-extra.raw"
            self.disk = {"size": f"{self.disk}G", "path": path}
            self.net_devices += f"""\n
<disk type='file' device='disk'>
    <driver name='qemu' type='raw'/>
    <source file='{path}'/>
    <target dev='vdz' bus='virtio'/>
</disk>\n"""

    def to_dict(self):
        d = super().to_dict()
        d.update(
            core=self.core,
            mem=self.mem,
            pm=self.pm.to_dict(),
            eui=str(self.eui),
            extra_devices=self.net_devices,
            disk=self.disk,
        )
        return d

    def __hash__(self):
        return int(self.eui)

    def __eq__(self, other):
        return int(self.eui) == int(other.eui)


class VMonG5k(Provider):
    """The provider to use when deploying virtual machines on Grid'5000."""

    def init(self, force_deploy=False):
        _force_deploy = self.provider_conf.force_deploy
        self.provider_conf.force_deploy = _force_deploy or force_deploy
        g5k_conf = _build_g5k_conf(self.provider_conf)
        g5k_provider = g5kprovider.G5k(g5k_conf)
        self.g5k_roles, self.g5k_networks = g5k_provider.init()
        g5k_subnets = self.g5k_networks["__subnet__"]

        # we concretize the virtualmachines
        for machine in self.provider_conf.machines:
            pms = self.g5k_roles[machine.cookie]
            machine.undercloud = pms

        roles, networks = start_virtualmachines(
            self.provider_conf,
            g5k_subnets,
            force_deploy=self.provider_conf.force_deploy,
        )
        return roles, networks

    def undercloud(self):
        """Gets the undercloud information (bare-metal machines)."""
        return self.g5k_roles, self.g5k_networks

    def destroy(self):
        pass

    def __str__(self):
        return "VMonG5k"
