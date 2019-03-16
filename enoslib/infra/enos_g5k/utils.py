# -*- coding: utf-8 -*-
from collections import defaultdict
import copy
import logging
import time

from execo import Host
import execo_g5k as ex5
import execo_g5k.api_utils as api

from enoslib.errors import EnosError
from enoslib.infra.enos_g5k import remote
from enoslib.infra.enos_g5k.error import (MissingNetworkError,
                                          NotEnoughNodesError)
from enoslib.infra.enos_g5k.schema import (PROD, KAVLAN_GLOBAL, KAVLAN_LOCAL,
                                           KAVLAN, KAVLAN_TYPE, SUBNET_TYPE)
from enoslib.infra.utils import pick_things, mk_pools


logger = logging.getLogger(__name__)


SYNCHRONISATION_OFFSET = 60


class EnosG5kDuplicateJobs(EnosError):
    def __init__(self, site, job_name):
        super(EnosG5kDuplicateJobs, self).__init__(
            "Duplicate jobs on %s with the same name %s"
            % (site, job_name)
        )


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
    if vlan_id < 10:
        return KAVLAN
    return KAVLAN_GLOBAL


def to_subnet_type(ip_prefix):
    return "slash_%s" % ip_prefix[-2:]


def _grid_reload_from_name(gk, job_name):
    sites = gk.sites.list()
    jobs = []
    for site in sites:
        logger.info("Reloading %s from %s" % (job_name, site.uid))
        _jobs = site.jobs.list(name=job_name,
                               state="waiting,launching,running")
        if len(_jobs) == 1:
            logger.info("Reloading %s from %s" % (_jobs[0].uid, site.uid))
            jobs.append(_jobs[0])
        elif len(_jobs) > 1:
            raise EnosG5kDuplicateJobs(site, job_name)
    return jobs


def _date2h(timestamp):
    t = time.strftime("%Y-%m-%d %H:%M:%S",
                      time.localtime(timestamp))
    return t


def wait_for_jobs(jobs):
    """Waits for all the jobs to be runnning."""

    all_running = False
    while not all_running:
        all_running = True
        time.sleep(5)
        for job in jobs:
            job.refresh()
            scheduled = getattr(job, "scheduled_at", None)
            if scheduled is not None:
                logger.info("Waiting for %s on %s [%s]" % (job.uid,
                                                           job.site,
                                                           _date2h(scheduled)))
            all_running = all_running and job.state == "running"
            if job.state == "error":
                raise Exception("The job %s is in error state" % job)
    logger.info("All jobs are Running !")


def grid_get_or_create_job(gk, job_name, walltime, reservation_date,
                           queue, job_type, machines, networks):
    jobs = _grid_reload_from_name(gk, job_name)
    if len(jobs) == 0:
        jobs = grid_make_reservation(gk, job_name, walltime, reservation_date,
                                        queue, job_type, machines, networks)
    wait_for_jobs(jobs)

    vlans = []
    subnets = []
    nodes = []
    for job in jobs:
        _subnets = job.resources_by_type.get("subnets", [])
        _vlans = job.resources_by_type.get("vlans", [])
        nodes = nodes + job.assigned_nodes
        # TODO FIXME networks
        subnets = subnets + [{"site": job.site,
                              "ipmac": "fillme"} for s in _subnets]
        vlans = vlans + [{"site": job.site,
                          "vlan_id": vlan_id} for vlan_id in _vlans]
    logger.debug("nodes=%s, subnets=%s, vlans=%s" % (nodes, subnets, vlans))

    return nodes, vlans, subnets


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
            if nic['mountable']
            and nic['interface'] == 'Ethernet'
            and not nic['management']
            and extra_cond(nic)]
    nics = sorted(nics)
    return nics


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


def _build_reservation_criteria(machines, networks):
    criteria = {}
    # machines reservations
    for desc in machines:
        cluster = desc["cluster"]
        nodes = desc["nodes"]
        if nodes:
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

    return criteria


def _do_submit_jobs(gk, job_specs):
    jobs = []
    try:
        for site, job_spec in job_specs:
            logging.info("Submitting %s on %s" % (job_spec, site))
            jobs.append(gk.sites[site].jobs.create(job_spec))
    except Error as e:
        logger.error("An error occured during the job submissions")
        logger.error("Cleaning the jobs created")
        for job in jobs:
            job.delete()
        raise(e)

    return jobs


def _do_grid_make_reservation(gk, criterias, job_name, walltime,
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

    jobs = _do_submit_jobs(gk, job_specs)
    return jobs


def _do_synchronise_jobs(gk, walltime, machines):
    """ This returns a common reservation date for all the jobs.

    This reservation date is really only a hint and will be supplied to each
    oar server. Without this *common* reservation_date, one oar server can
    decide to postpone the start of the job while the other are already
    running. But this doens't prevent the start of a job on one site to drift
    (e.g because the machines need to be restarted.) But this shouldn't exceed
    few minutes.
    """

    def _clusters_sites(gk, clusters):
        _clusters = copy.deepcopy(clusters)
        sites = gk.sites.list()
        matches = {}
        for site in sites:
            candidates = site.clusters.list()
            matching = [c.uid for c in candidates if c.uid in _clusters]
            if len(matching) == 1:
                matches[matching[0]] = site
                _clusters.remove(matching[0])
        return matches

    offset = SYNCHRONISATION_OFFSET
    start = time.time() + offset
    _t = time.strptime(walltime, "%H:%M:%S")
    _walltime = _t.tm_hour * 3600 + _t.tm_min * 60 + _t.tm_sec

    # Compute the demand for each cluster
    demands = defaultdict(int)
    for machine in machines:
        cluster = machine["cluster"]
        demands[cluster] += machine["nodes"]

    # Early leave if only one cluster is there
    if len(list(demands.keys())) <= 1:
        logger.debug("Only one cluster detected: no synchronisation needed")
        return None

    clusters = _clusters_sites(gk, list(demands.keys()))

    # Early leave if only one site is concerned
    sites = set(list(clusters.values()))
    if len(sites) <= 1:
        logger.debug("Only one site detected: no synchronisation needed")
        return None

    # Test the proposed reservation_date
    ok = True
    for cluster, nodes in demands.items():
        cluster_status = clusters[cluster].status.list()
        ok = ok and can_start_on_cluster(cluster_status.nodes,
                                         nodes,
                                         start,
                                         _walltime)
        if not ok:
            break
    if ok:
        # The proposed reservation_date fits
        logger.info("Reservation_date=%s (%s)" % (_date2h(start), sites))
        return start

    return None


def grid_make_reservation(gk, job_name, walltime, reservation_date,
                          queue, job_type, machines, networks):
    if not reservation_date:
        # First check if synchronisation is required
        reservation_date = _do_synchronise_jobs(gk, walltime, machines)

    # Build the OAR criteria
    criteria = _build_reservation_criteria(machines, networks)

    # Submit them
    jobs = _do_grid_make_reservation(gk, criteria, job_name, walltime,
                                        reservation_date, queue, job_type)

    return jobs


def grid_destroy_from_name(gk, job_name):
    """Destroy the job."""
    jobs = _grid_reload_from_name(gk, job_name)
    for job in jobs:
        job.delete()
        logger.info("Killing the job (%s, %s)" % (job.site, job.uid))


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


def can_start_on_cluster(nodes_status,
                         nodes,
                         start,
                         walltime):
    """Check if #nodes can be started on a given cluster.

    This is intended to give a good enough approximation.
    This can be use to prefiltered possible reservation dates before submitting
    them on oar.
    """
    candidates = []
    for node, status in nodes_status.items():
        reservations = status.get("reservations", [])
        # we search for the overlapping reservations
        overlapping_reservations = []
        for reservation in reservations:
            queue = reservation.get("queue")
            if queue == "besteffort":
                # ignoring any besteffort reservation
                continue
            r_start = reservation.get("started_at",
                                      reservation.get("scheduled_at"))
            if r_start is None:
                break
            r_start = int(r_start)
            r_end = r_start + int(reservation["walltime"])
            # compute segment intersection
            _intersect = min(r_end, start + walltime) - max(r_start, start)
            if _intersect > 0:
                overlapping_reservations.append(reservation)
        if len(overlapping_reservations) == 0:
            # this node can be accounted for a potential reservation
            candidates.append(node)
    if len(candidates) >= nodes:
        return True
    return False
