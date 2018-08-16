# -*- coding: utf-8 -*-
import logging

from execo import Host
import execo_g5k as ex5
import execo_g5k.api_utils as api

from enoslib.infra.enos_g5k import remote
from enoslib.infra.enos_g5k.error import (MissingNetworkError,
                                          NotEnoughNodesError)
from enoslib.infra.enos_g5k.schema import (PROD, KAVLAN_GLOBAL, KAVLAN_LOCAL,
                                           KAVLAN, KAVLAN_TYPE, SUBNET_TYPE)
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
        cmd = ["cat ~/.ssh/id_rsa.pub"]
        cmd.append("sudo-g5k tee -a /root/.ssh/authorized_keys")
        cmd = "|".join(cmd)
        remote.exec_command_on_nodes(desc["_c_nodes"],
                                     cmd, cmd, conn_params={})


def is_prod(network, networks):
    net = lookup_networks(network, networks)
    return net["type"] == PROD


def to_vlan_type(vlan_id):
    if vlan_id < 4:
        return KAVLAN_LOCAL
    elif vlan_id < 10:
        return KAVLAN
    return KAVLAN_GLOBAL


def to_subnet_type(ip_prefix):
    return "slash_%s" % ip_prefix[-2:]


def grid_get_or_create_job(job_name, walltime, reservation_date,
                      queue, job_type, machines, networks):
    gridjob, _ = ex5.planning.get_job_by_name(job_name)
    if gridjob is None:
        gridjob = grid_make_reservation(job_name, walltime, reservation_date,
                                        queue, job_type, machines, networks)
    logger.info("Waiting for oargridjob %s to start" % gridjob)
    ex5.wait_oargrid_job_start(gridjob)
    return gridjob


def get_network_info_from_job_id(job_id, site, vlans, subnets):
    vlan_ids = ex5.get_oar_job_kavlan(job_id, site)
    vlans.extend([{
        "site": site,
        "vlan_id": vlan_id} for vlan_id in vlan_ids])
    # NOTE(msimonin): this currently returned only one subnet
    # even if several are reserved
    # We'll need to patch execo the same way it has been patched for vlans
    ipmac, info = ex5.get_oar_job_subnets(job_id, site)
    if not ipmac:
        logger.debug("No subnet information found for this job")
        return vlans, subnets
    subnet = {
        "site": site,
        "ipmac": ipmac,
    }
    subnet.update(info)
    # Mandatory key when it comes to concretize resources
    subnet.update({"network": info["ip_prefix"]})
    subnets.append(subnet)
    return vlans, subnets


def grid_reload_from_id(gridjob):
    logger.info("Reloading the resources from oargrid job %s", gridjob)
    gridjob = int(gridjob)
    nodes = ex5.get_oargrid_job_nodes(gridjob)

    job_sites = ex5.get_oargrid_job_oar_jobs(gridjob)
    vlans = []
    subnets = []
    for (job_id, site) in job_sites:
        vlans, subnets = get_network_info_from_job_id(job_id,
                                                      site,
                                                      vlans,
                                                      subnets)
    return nodes, vlans, subnets


def oar_reload_from_id(oarjob, site):
    logger.info("Reloading the resources from oar job %s", oarjob)
    job_id = int(oarjob)
    nodes = ex5.get_oar_job_nodes(job_id)

    vlans = []
    subnets = []
    vlans, subnets = get_network_info_from_job_id(job_id,
                                                  site,
                                                  vlans,
                                                  subnets)
    return nodes, vlans, subnets


def _deploy(nodes, force_deploy, options):
    # For testing purpose
    logger.info("Deploying %s with options %s" % (nodes, options))
    dep = ex5.Deployment(nodes, **options)
    return ex5.deploy(dep, check_deployed_command=not force_deploy)


def mount_nics(c_resources):
    machines = c_resources["machines"]
    networks = c_resources["networks"]
    for desc in machines:
        _, nic_name = get_cluster_interfaces(desc["cluster"],
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
    nics = get_cluster_interfaces(cluster, lambda nic: not nic['mounted'])
    idx = 0
    desc["_c_nics"] = desc.get("_c_nics") or []
    for network_id in desc.get("secondary_networks", []):
        net = lookup_networks(network_id, networks)
        if net["type"] == PROD:
            # nothing to do
            continue
        nic_device, nic_name = nics[idx]
        nodes_to_set = [Host(n) for n in desc["_c_nodes"]]
        vlan_id = net["_c_network"]["vlan_id"]
        logger.info("Put %s, %s in vlan id %s for nodes %s" %
                    (nic_device, nic_name, vlan_id, nodes_to_set))
        api.set_nodes_vlan(net["site"],
                           nodes_to_set,
                           nic_device,
                           vlan_id)
        # recording the mapping, just in case
        desc["_c_nics"].append((nic_name, get_roles_as_list(net)))
        idx = idx + 1


def get_cluster_site(cluster):
    return ex5.get_cluster_site(cluster)


def get_cluster_interfaces(cluster, extra_cond=lambda nic: True):
    site = ex5.get_cluster_site(cluster)
    nics = ex5.get_resource_attributes(
        "/sites/%s/clusters/%s/nodes" % (site, cluster))
    nics = nics['items'][0]['network_adapters']
    # NOTE(msimonin): Since 05/18 nics on g5k nodes have predictable names but
    # the api description keep the legacy name (device key) and the new
    # predictable name (key name).  The legacy names is still used for api
    # request to the vlan endpoint This should be fixed in
    # https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=9272
    # When its fixed we should be able to only use the new predictable name.
    nics = [(nic['device'], nic['name']) for nic in nics
           if nic['mountable'] and
           nic['interface'] == 'Ethernet' and
           not nic['management'] and extra_cond(nic)]
    nics = sorted(nics)
    return nics


def lookup_networks(network_id, networks):
    match = [net for net in networks if net["id"] == network_id]
    # if it has been validated the following is valid
    return match[0]


def concretize_nodes(resources, nodes):
    # force order to be a *function*
    snodes = sorted(nodes, key=lambda n: n.address)
    pools = mk_pools(snodes, lambda n: n.address.split('-')[0])

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
        desc["_c_nodes"] = [c_node.address for c_node in c_nodes]

    # We then fill the remaining without
    # If no enough nodes are there we silently continue
    for desc in machines:
        cluster = desc["cluster"]
        nb = desc["nodes"] - len(desc["_c_nodes"])
        c_nodes = pick_things(pools, cluster, nb)
        #  put concrete hostnames here
        desc["_c_nodes"].extend([c_node.address for c_node in c_nodes])
    return resources


def concretize_networks(resources, vlans, subnets):
    # avoid any non-determinism
    s_vlans = sorted(vlans, key=lambda v: (v["site"], v["vlan_id"]))
    s_subnets = sorted(subnets, key=lambda s: (s["site"], s["ip_prefix"]))
    pools = mk_pools(
        s_vlans,
        lambda n: (n["site"], to_vlan_type(n["vlan_id"])))
    pools_subnets = mk_pools(
        s_subnets,
        lambda n: (n["site"], to_subnet_type(n["ip_prefix"])))

    for desc in resources["networks"]:
        site = desc["site"]
        site_info = ex5.get_resource_attributes('/sites/%s' % site)
        n_type = desc["type"]
        if n_type == PROD:
            desc["_c_network"] = {"site": site, "vlan_id": None}
            desc["_c_network"].update(site_info["kavlans"]["default"])
        elif n_type in KAVLAN_TYPE:
            networks = pick_things(pools, (site, n_type), 1)
            if len(networks) < 1:
                raise MissingNetworkError(site, n_type)
            # concretize the network
            desc["_c_network"] = networks[0]
            vlan_id = desc["_c_network"]["vlan_id"]
            desc["_c_network"].update(site_info["kavlans"][str(vlan_id)])
        elif n_type in SUBNET_TYPE:
            networks = pick_things(pools_subnets, (site, n_type), 1)
            if len(networks) < 1:
                raise MissingNetworkError(site, n_type)
            desc["_c_network"] = networks[0]

    return resources


def grid_make_reservation(job_name, walltime,
                     reservation_date, queue, job_type, machines, networks):
    criteria = {}
    # machines reservations
    for desc in machines:
        cluster = desc["cluster"]
        nodes = desc["nodes"]
        site = api.get_cluster_site(cluster)
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

    jobs_specs = [(ex5.OarSubmission(resources='+'.join(c),
                                     name=job_name), s)
                  for s, c in criteria.items()]

    # Make the reservation
    gridjob, _ = ex5.oargridsub(
        jobs_specs,
        walltime=walltime,
        reservation_date=reservation_date,
        job_type=job_type,
        queue=queue)

    if gridjob is None:
        raise Exception('No oar job was created')
    return gridjob


def grid_destroy_from_name(job_name):
    """Destroy the job."""
    gridjob, _ = ex5.planning.get_job_by_name(job_name)
    if gridjob is not None:
        ex5.oargriddel([gridjob])
        logger.info("Killing the job %s" % gridjob)


def grid_destroy_from_id(gridjob):
    """Destroy the job."""
    gridjob = int(gridjob)
    if gridjob is not None:
        ex5.oargriddel([gridjob])
        logger.info("Killing the job %s" % gridjob)


def oar_destroy_from_id(oarjob, site):
    """Destroy the job."""
    oarjob = int(oarjob)
    if oarjob is not None and site is not None:
        ex5.oardel([[oarjob, site]])
        logger.info("Killing the job %s" % oarjob)
