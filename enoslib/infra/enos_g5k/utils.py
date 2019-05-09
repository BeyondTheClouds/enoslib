# -*- coding: utf-8 -*-
import logging

import enoslib.infra.enos_g5k.g5k_api_utils as g5k_api_utils
from enoslib.infra.enos_g5k.error import (MissingNetworkError,
                                          NotEnoughNodesError)
from enoslib.infra.enos_g5k import remote
from enoslib.infra.enos_g5k.constants import (PROD, KAVLAN_TYPE, SUBNET_TYPES,
                                              SLASH_16, SLASH_22)
from enoslib.infra.utils import pick_things, mk_pools


logger = logging.getLogger(__name__)


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


def grid_get_or_create_job(job_name, walltime, reservation_date,
                           queue, job_type, machines, networks):
    jobs = g5k_api_utils.grid_reload_from_name(job_name)
    if len(jobs) == 0:
        jobs = grid_make_reservation(job_name, walltime, reservation_date,
                                     queue, job_type, machines, networks)
    g5k_api_utils.wait_for_jobs(jobs)

    return g5k_api_utils.build_resources(jobs)


def grid_reload_from_ids(oarjobids):
    logger.info("Reloading the resources from oar jobs %s", oarjobids)
    jobs = g5k_api_utils.grid_reload_from_ids(oarjobids)

    g5k_api_utils.wait_for_jobs(jobs)

    return g5k_api_utils.build_resources(jobs)


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
        # There can be only one here...
        vlan_id = net["_c_network"][0].vlan_id
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
    """Maps abstract to concrete networks.

    Warning:
        Side effect on resources
    """
    s_networks = sorted(networks, key=lambda n: (n.site, n.nature, n.network))
    pools = mk_pools(
        s_networks,
        lambda n: (n.site, n.nature))
    for desc in resources["networks"]:
        site = desc["site"]
        n_type = desc["type"]
        # On grid'5000 a slash_16 is 64 slash_22
        # So if we ask for a slash_16 we return 64 sash_22
        # yes, this smells
        if n_type == SLASH_16:
            _networks = pick_things(pools, (site, SLASH_22), 64)
        else:
            _networks = pick_things(pools, (site, n_type), 1)
        if len(_networks) < 1:
            raise MissingNetworkError(site, n_type)
        desc["_c_network"] = _networks

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
               if network["type"] in SUBNET_TYPES]
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
