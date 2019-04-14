# -*- coding: utf-8 -*-
import logging

from netaddr import IPAddress, IPNetwork, IPSet

from enoslib.infra.enos_g5k.constants import G5KMACPREFIX, NATURE_PROD
import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from enoslib.infra.enos_g5k.error import (MissingNetworkError,
                                          NotEnoughNodesError)
from enoslib.infra.enos_g5k import remote
from enoslib.infra.enos_g5k.schema import (PROD, KAVLAN_GLOBAL, KAVLAN_LOCAL,
                                           KAVLAN, KAVLAN_TYPE, SUBNET_TYPE)
from enoslib.infra.utils import pick_things, mk_pools


logger = logging.getLogger(__name__)


class ConcreteNetwork:
    def __init__(self, *,
                 site=None,
                 network=None,
                 gateway=None,
                 dns=None,
                 vlan_id=None,
                 ipmac=None,
                 nature=None,
                 **kwargs):
        self.site = site
        self.network = network
        self.gateway = gateway
        # NOTE(msimonin): dns info isn't present in g5k api
        self.dns = dns
        self.vlan_id = vlan_id
        self.ipmac = []
        if ipmac is not None:
            self.ipmac = ipmac

        self.nature = nature

    @staticmethod
    def to_nature(n_type):
        return n_type

    @staticmethod
    def get_dns(site_info):
        return site_info.servers["dns"].network_adapters["default"]["ip"]

    def __repr__(self):
        return ("<ConcreteNetwork site=%s"
                                " nature=%s"
                                " network=%s"
                                " gateway=%s"
                                " dns=%s"
                                " vlan_id=%s>") % (
                                    self.site,
                                    self.nature,
                                    self.network,
                                    self.gateway,
                                    self.dns,
                                    self.vlan_id)


class ConcreteSubnet(ConcreteNetwork):

    @staticmethod
    def to_nature(subnet):
        return "slash_%s" % subnet[-2:]

    @classmethod
    def from_job(cls, site_info, subnet):
        ipmac = []
        network = IPNetwork(subnet)
        for ip in network[1:-1]:
            _, x, y, z = ip.words
            ipmac.append((str(ip),
                          G5KMACPREFIX + ":%02X:%02X:%02X" % (x, y, z)))
        nature = ConcreteSubnet.to_nature(subnet)

        kwds = {
            "nature": nature,
            "gateway": site_info.g5ksubnet["gateway"],
            "network": subnet,
            "site": site_info.uid,
            "ipmac": ipmac,
            "dns": cls.get_dns(site_info)
        }
        return cls(**kwds)

    def to_enos(self, roles):
        net = {}
        start_ip, start_mac = self.ipmac[0]
        end_ip, end_mac = self.ipmac[-1]
        net.update(start=start_ip,
                   end=end_ip,
                   mac_start=start_mac,
                   mac_end=end_mac,
                   roles=roles,
                   cidr=self.network,
                   gateway=self.gateway,
                   dns=self.dns)
        return net


class ConcreteVlan(ConcreteNetwork):

    kavlan_local = ["1", "2", "3"]
    kavlan = ["4", "5", "6", "7", "8", "9"]

    @staticmethod
    def to_nature(vlan_id):
        if vlan_id in ConcreteVlan.kavlan_local:
            return KAVLAN_LOCAL
        if vlan_id in ConcreteVlan.kavlan:
            return KAVLAN
        return KAVLAN_GLOBAL

    @classmethod
    def from_job(cls, site_info, vlan_id):

        nature = ConcreteVlan.to_nature(vlan_id)
        kwds = {
            "nature": nature,
            "vlan_id": str(vlan_id),
            "dns": cls.get_dns(site_info)
        }
        kwds.update(site_info.kavlans[str(vlan_id)])
        kwds.update(site=site_info.uid)
        return cls(**kwds)

    def to_enos(self, roles):
        # On the network, the first IP are reserved to g5k machines.
        # For a routed vlan I don't know exactly how many ip are
        # reserved. However, the specification is clear about global
        # vlan: "A global VLAN is a /18 subnet (16382 IP addresses).
        # It is split -- contiguously -- so that every site gets one
        # /23 (510 ip) in the global VLAN address space". There are 12
        # site. This means that we could take ip from 13th subnetwork.
        # Lets consider the strategy is the same for routed vlan. See,
        # https://www.grid5000.fr/mediawiki/index.php/Grid5000:Network#KaVLAN
        #
        # First, split network in /23 this leads to 32 subnetworks.
        # Then, (i) drops the 12 first subnetworks because they are
        # dedicated to g5k machines, and (ii) drops the last one
        # because some of ips are used for specific stuff such as
        # gateway, kavlan server...
        net = {}
        subnets = IPNetwork(self.network)
        if self.vlan_id in ConcreteVlan.kavlan_local:
            # vlan local
            subnets = list(subnets.subnet(24))
            subnets = subnets[4:7]
        else:
            subnets = list(subnets.subnet(23))
            subnets = subnets[13:31]

        # Finally, compute the range of available ips
        ips = IPSet(subnets).iprange()

        net.update(start=str(IPAddress(ips.first)),
                   end=str(IPAddress(ips.last)),
                   cidr=self.network,
                   gateway=self.gateway,
                   dns=self.dns,
                   roles=roles)
        return net


class ConcreteProd(ConcreteNetwork):

    @classmethod
    def from_job(cls, site_info):
        nature = NATURE_PROD
        vlan_id = "default"
        kwds = {
            "nature": nature,
            "vlan_id": str(vlan_id),
            "site": site_info.uid,
            "dns": cls.get_dns(site_info)
        }
        kwds.update(site_info.kavlans[vlan_id])
        return cls(**kwds)

    def to_enos(self, roles):
        net = {}
        net.update(cidr=self.network,
                   gateway=self.gateway,
                   dns=self.dns,
                   roles=roles)
        return net


def dhcp_interfaces(c_resources):
    # TODO(msimonin) add a filter
    machines = c_resources["machines"]
    for desc in machines:
        nics = desc.get("_c_nics", [])
        nics_list = [nic for nic, _ in nics]
        ifconfig = ["ip link set %s up" % nic for nic in nics_list]
        dhcp = ["dhclient %s" % nic for nic in nics_list]
        cmd = "%s ; %s" % (";".join(ifconfig), ";".join(dhcp))
        remote.exec_command_on_nodes(desc["_c_ssh_nodes"],
                                     cmd, cmd)


def grant_root_access(c_resources):
    machines = c_resources["machines"]
    for desc in machines:
        cmd = ["cat ~/.ssh/id_rsa.pub ~/.ssh/authorized_keys"]
        cmd.append("sudo-g5k tee -a /root/.ssh/authorized_keys")
        cmd = "|".join(cmd)
        remote.exec_command_on_nodes(desc["_c_nodes"],
                                     cmd, cmd, conn_params={})


def is_prod(network, networks):
    net = lookup_networks(network, networks)
    return net["type"] == PROD


def _build_resources(jobs):
    gk = g5k_api_utils.get_api_client()
    nodes = []
    networks = []
    for job in jobs:
        # Ok so we build the networks given by g5k for each job
        # a network is here a dict
        _subnets = job.resources_by_type.get("subnets", [])
        _vlans = job.resources_by_type.get("vlans", [])
        nodes = nodes + job.assigned_nodes
        site_info = gk.sites[job.site]

        networks += [ConcreteSubnet.from_job(site_info, subnet)
                     for subnet in _subnets]
        networks += [ConcreteVlan.from_job(site_info, vlan_id)
                     for vlan_id in _vlans]
        networks += [ConcreteProd.from_job(site_info)]

    logger.debug("nodes=%s, networks=%s" % (nodes, networks))
    return nodes, networks


def grid_get_or_create_job(job_name, walltime, reservation_date,
                           queue, job_type, machines, networks):
    jobs = g5k_api_utils.grid_reload_from_name(job_name)
    if len(jobs) == 0:
        jobs = grid_make_reservation(job_name, walltime, reservation_date,
                                     queue, job_type, machines, networks)
    g5k_api_utils.wait_for_jobs(jobs)

    return _build_resources(jobs)


def grid_reload_from_ids(oarjobids):
    logger.info("Reloading the resources from oar jobs %s", oarjobids)
    jobs = g5k_api_utils.grid_reload_from_ids(oarjobids)

    g5k_api_utils.wait_for_jobs(jobs)

    return _build_resources(jobs)


def mount_nics(c_resources):
    machines = c_resources["machines"]
    networks = c_resources["networks"]
    for desc in machines:
        _, nic_name = g5k_api_utils.get_cluster_interfaces(
            desc["cluster"],
            lambda nic: nic['mounted'])[0]
        net = lookup_networks(desc["primary_network"], networks)
        desc["_c_nics"] = [(nic_name, get_roles_as_list(net))]
        _mount_secondary_nics(desc, networks)
    return c_resources


def get_roles_as_list(desc):
    roles = desc.get("role", [])
    if roles:
        roles = [roles]
    roles.extend(desc.get("roles", []))
    return roles


def _mount_secondary_nics(desc, networks):
    cluster = desc["cluster"]
    # get only the secondary interfaces
    nics = g5k_api_utils.get_cluster_interfaces(cluster,
                                                lambda nic: not nic['mounted'])
    idx = 0
    desc["_c_nics"] = desc.get("_c_nics") or []
    for network_id in desc.get("secondary_networks", []):
        net = lookup_networks(network_id, networks)
        if net["type"] == PROD:
            # nothing to do
            continue
        nic_device, nic_name = nics[idx]
        vlan_id = net["_c_network"].vlan_id
        logger.info("Put %s, %s in vlan id %s for nodes %s" %
                    (nic_device, nic_name, vlan_id, desc["_c_nodes"]))
        g5k_api_utils.set_nodes_vlan(net["site"],
                                     desc["_c_nodes"],
                                     nic_device,
                                     vlan_id)
        # recording the mapping, just in case
        desc["_c_nics"].append((nic_name, get_roles_as_list(net)))
        idx = idx + 1


def lookup_networks(network_id, networks):
    match = [net for net in networks if net["id"] == network_id]
    # if it has been validated the following is valid
    return match[0]


def concretize_nodes(resources, nodes):
    # force order to be a *function*
    snodes = sorted(nodes, key=lambda n: n)
    pools = mk_pools(snodes, lambda n: n.split('-')[0])

    # We first try to fulfill min requirements
    # Just considering machines with min value specified
    machines = resources["machines"]
    min_machines = sorted(machines, key=lambda desc: desc.get("min", 0))
    for desc in min_machines:
        cluster = desc["cluster"]
        nb = desc.get("min", 0)
        c_nodes = pick_things(pools, cluster, nb)
        if len(c_nodes) < nb:
            raise NotEnoughNodesError("min requirement failed for %s " % desc)
        desc["_c_nodes"] = [c_node for c_node in c_nodes]

    # We then fill the remaining without
    # If no enough nodes are there we silently continue
    for desc in machines:
        cluster = desc["cluster"]
        nb = desc["nodes"] - len(desc["_c_nodes"])
        c_nodes = pick_things(pools, cluster, nb)
        #  put concrete hostnames here
        desc["_c_nodes"].extend([c_node for c_node in c_nodes])
    return resources


def concretize_networks(resources, networks):
    # avoid any non-determinism
    s_networks = sorted(networks, key=lambda n: (n.site, n.nature, n.network))
    pools = mk_pools(
        s_networks,
        lambda n: (n.site, n.nature))
    for desc in resources["networks"]:
        site = desc["site"]
        n_type = desc["type"]
        _networks = pick_things(pools, (site, n_type), 1)
        if len(_networks) < 1:
            raise MissingNetworkError(site, n_type)
        desc["_c_network"] = _networks[0]

    return resources


def _build_reservation_criteria(machines, networks):
    criteria = {}
    # machines reservations
    for desc in machines:
        cluster = desc["cluster"]
        nodes = desc["nodes"]
        if nodes:
            site = g5k_api_utils.get_cluster_site(cluster)
            criterion = "{cluster='%s'}/nodes=%s" % (cluster, nodes)
            criteria.setdefault(site, []).append(criterion)

    # network reservations
    vlans = [network for network in networks
             if network["type"] in KAVLAN_TYPE]
    for desc in vlans:
        site = desc["site"]
        n_type = desc["type"]
        criterion = "{type='%s'}/vlan=1" % n_type
        criteria.setdefault(site, []).append(criterion)

    subnets = [network for network in networks
               if network["type"] in SUBNET_TYPE]
    for desc in subnets:
        site = desc["site"]
        n_type = desc["type"]
        criterion = "%s=1" % n_type
        criteria.setdefault(site, []).append(criterion)

    return criteria


def _do_grid_make_reservation(criterias, job_name, walltime,
                              reservation_date, queue, job_type):
    job_specs = []
    for site, criteria in criterias.items():
        resources = "+".join(criteria)
        resources = "%s,walltime=%s" % (resources, walltime)
        job_spec = {"name": job_name,
                     "types": [job_type],
                     "resources": resources,
                     "command": "sleep 31536000",
                     "queue": queue}
        if reservation_date:
            job_spec.update(reservation=reservation_date)
        job_specs.append((site, job_spec))

    jobs = g5k_api_utils.submit_jobs(job_specs)
    return jobs


def grid_make_reservation(job_name, walltime, reservation_date,
                          queue, job_type, machines, networks):
    if not reservation_date:
        # First check if synchronisation is required
        reservation_date = g5k_api_utils._do_synchronise_jobs(walltime,
                                                              machines)

    # Build the OAR criteria
    criteria = _build_reservation_criteria(machines, networks)

    # Submit them
    jobs = _do_grid_make_reservation(criteria, job_name, walltime,
                                        reservation_date, queue, job_type)

    return jobs