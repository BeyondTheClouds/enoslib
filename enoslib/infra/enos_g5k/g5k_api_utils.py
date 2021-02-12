"""
This module is composed of helpers functions to deal with the Grid'5000 REST
API.

It wraps the python-grid5000 library to provide some usual routines to interact
with the platform.
"""

from collections import defaultdict, namedtuple

import logging
from grid5000.objects import Job, Node, Vlan
import os
import time
import threading
from typing import Dict, Any, List, Tuple
from pathlib import Path

from .error import (
    EnosG5kDuplicateJobsError,
    EnosG5kSynchronisationError,
    EnosG5kWalltimeFormatError,
)
from .constants import (
    KAVLAN_GLOBAL,
    KAVLAN_IDS,
    KAVLAN_LOCAL,
    KAVLAN,
    KAVLAN_LOCAL_IDS,
    PROD_VLAN_ID,
    SYNCHRONISATION_OFFSET,
    NATURE_PROD,
    MAX_DEPLOY,
)

import diskcache
from grid5000 import Grid5000
import ring


storage = diskcache.Cache("cachedir")

logger = logging.getLogger(__name__)


_api_lock = threading.Lock()
# Keep track of the api client
_api_client = None

# Poor man's cache (for now)
_cache_lock = threading.RLock()
cache: Dict[Any, Any] = {}


class Client(Grid5000):
    """Wrapper of the python-grid5000 client.

    It accepts extra parameters to be set in the configuration file.
    """

    def __init__(self, excluded_sites=None, **kwargs):
        """Constructor.

        Args:
            excluded_sites(list): sites to forget about when reloading the
                jobs. The primary use case was to exclude unreachable sites and
                allow the program to go on.
        """
        super().__init__(**kwargs)
        self.excluded_site = excluded_sites
        if excluded_sites is None:
            self.excluded_site = []


# Lighweight reprentation of a network returned by OAR
# descriptor is the cidr for a subnet or an id for vlan (prod=="DEFAULT")
OarNetwork = namedtuple("OarNetwork", ["site", "nature", "descriptor"])


def to_vlan_nature(vlan_id: str) -> str:
    # TODO(msimonin): replace that by an api call to get the nature
    if vlan_id in KAVLAN_LOCAL_IDS:
        return KAVLAN_LOCAL
    if vlan_id in KAVLAN_IDS:
        return KAVLAN
    return KAVLAN_GLOBAL


def to_subnet_nature(cidr: str) -> str:
    return "slash_%s" % cidr[-2:]


def to_prod_nature() -> str:
    return "DEFAULT"


def get_api_client():
    """Gets the reference to the API cient (singleton)."""
    with _api_lock:
        global _api_client
        if not _api_client:
            conf_file = os.path.join(os.environ.get("HOME"), ".python-grid5000.yaml")
            _api_client = Client.from_yaml(conf_file)

        return _api_client


def _date2h(timestamp):
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    return t


def grid_reload_from_name(job_name):
    """Reload all running or pending jobs of Grid'5000 with a given name.

    By default all the sites will be searched for jobs with the name
    ``job_name``. Using EnOSlib there can be only one job per site with name
    ``job_name``.

    Note that it honors the ``exluded_sites`` attribute of the client so the
    scan can be reduced.

    Args:
        job_name (str): the job name


    Returns:
        The list of the python-grid5000 jobs retrieved.

    Raises:
        EnosG5kDuplicateJobsError: if there's several jobs with the same name
            on a site.
    """
    gk = get_api_client()
    sites = get_all_sites_obj()
    jobs = []
    for site in [s for s in sites if s.uid not in gk.excluded_site]:
        logger.info("Reloading %s from %s" % (job_name, site.uid))
        _jobs = site.jobs.list(
            name=job_name, state="waiting,launching,running", user=get_api_username()
        )
        if len(_jobs) == 1:
            logger.info("Reloading %s from %s" % (_jobs[0].uid, site.uid))
            jobs.append(_jobs[0])
        elif len(_jobs) > 1:
            raise EnosG5kDuplicateJobsError(site, job_name)
    return jobs


def grid_reload_from_ids(oargrid_jobids):
    """Reload all running or pending jobs of Grid'5000 from their ids

    Args:
        oargrid_jobids (list): list of ``(site, oar_jobid)`` identifying the
            jobs on each site

    Returns:
        The list of python-grid5000 jobs retrieved
    """
    gk = get_api_client()
    jobs = []
    for site, job_id in oargrid_jobids:
        jobs.append(gk.sites[site].jobs[job_id])

    wait_for_jobs(jobs)

    return build_resources(jobs)


def build_resources(jobs: List[Job]) -> Tuple[List[str], List[OarNetwork]]:
    """Build the resources from the list of jobs.

    Args:
        jobs(list): The list of python-grid5000 jobs

    Returns:
        nodes, networks tuple where
            - nodes is a list of all the nodes of the various reservations
            - networks is a list of all the networks of the various reservation
    """
    nodes: List[str] = []
    networks: List[OarNetwork] = []
    for job in jobs:
        # can have several subnet like this (e.g when requesting a /16)
        # [...]
        # "subnets": [
        #     "10.158.0.0/22",
        #       ...,
        # ]
        _subnets = job.resources_by_type.get("subnets", [])
        # [...]
        # "vlans": [
        #     "4"
        # ]
        _vlans = job.resources_by_type.get("vlans", [])
        nodes = nodes + job.assigned_nodes
        site = job.site
        networks += [
            OarNetwork(site=site, nature=to_subnet_nature(subnet), descriptor=subnet)
            for subnet in _subnets
        ]
        networks += [
            OarNetwork(
                site=site, nature=to_vlan_nature(vlan_id), descriptor=str(vlan_id)
            )
            for vlan_id in _vlans
        ]
        # always add the Production network
        networks += [OarNetwork(site=site, nature=NATURE_PROD, descriptor=PROD_VLAN_ID)]

    logger.debug("nodes=%s, networks=%s" % (nodes, networks))
    return nodes, networks


def grid_destroy_from_name(job_name):
    """Destroy all the jobs with a given name.

    Args:
       job_name (str): the job name
    """
    jobs = grid_reload_from_name(job_name)
    for job in jobs:
        job.delete()
        logger.info("Killing the job (%s, %s)" % (job.site, job.uid))


def grid_destroy_from_ids(oargrid_jobids):
    """Destroy all the jobs with corresponding ids

    Args:
        oargrid_jobids (list): the ``(site, oar_job_id)`` list of tuple
            identifying the jobs for each site."""
    jobs = grid_reload_from_ids(oargrid_jobids)
    for job in jobs:
        job.delete()
        logger.info("Killing the jobs %s" % oargrid_jobids)


def submit_jobs(job_specs):
    """Submit a job

    Args:
        job_spec (dict): The job specifiation (see Grid'5000 API reference)
    """
    gk = get_api_client()
    jobs = []
    try:
        for site, job_spec in job_specs:
            logger.info("Submitting %s on %s" % (job_spec, site))
            jobs.append(gk.sites[site].jobs.create(job_spec))
    except Exception as e:
        logger.error("An error occured during the job submissions")
        logger.error("Cleaning the jobs created")
        for job in jobs:
            job.delete()
        raise (e)

    return jobs


def wait_for_jobs(jobs):
    """Waits for all the jobs to be runnning.

    Args:
        jobs(list): list of the python-grid5000 jobs to wait for


    Raises:
        Exception: if one of the job gets in error state.
    """

    all_running = False
    while not all_running:
        all_running = True
        time.sleep(5)
        for job in jobs:
            job.refresh()
            scheduled = getattr(job, "scheduled_at", None)
            if scheduled is not None:
                logger.info(
                    "Waiting for %s on %s [%s]"
                    % (job.uid, job.site, _date2h(scheduled))
                )
            all_running = all_running and job.state == "running"
            if job.state == "error":
                raise Exception("The job %s is in error state" % job)
    logger.info("All jobs are Running !")


def _deploy(
    site: str, deployed: List[str], undeployed: List[str], count: int, config: Dict
) -> Tuple[List[str], List[str]]:
    logger.info(
        "Deploying %s with options %s [%s/%s]", undeployed, config, count, MAX_DEPLOY
    )
    if count >= MAX_DEPLOY or len(undeployed) == 0:
        return deployed, undeployed

    d, u = deploy(site, undeployed, config)

    return _deploy(site, deployed + d, u, count + 1, config)


def grid_deploy(site: str, nodes: List[str], config: Dict):
    """Deploy and wait for the deployment to be finished.

    Args:
        site(str): the site
        nodes(list): list of nodes (str) to depoy
        options(dict): option of the deployment (refer to the Grid'5000 API
            Specifications)

    Returns:
        tuple of deployed(list), undeployed(list) nodes.
    """

    key_path = Path(config["key"]).expanduser().resolve()
    if not key_path.is_file():
        raise Exception("The public key file %s is not correct." % key_path)
    logger.info("Deploy the public key contained in %s to remote hosts.", key_path)
    config.update(key=key_path.read_text())
    return _deploy(site, [], nodes, 0, config)


def set_nodes_vlan(site, nodes, interface, vlan_id):
    """Set the interface of the nodes in a specific vlan.

    It is assumed that the same interface name is available on the node.

    Args:
        site(str): site to consider
        nodes(list): nodes to consider
        interface(str): the network interface to put in the vlan
        vlan_id(str): the id of the vlan
    """

    def _to_network_address(host):
        """Translate a host to a network address
        e.g:
        paranoia-20.rennes.grid5000.fr -> paranoia-20-eth2.rennes.grid5000.fr
        """
        splitted = host.split(".")
        splitted[0] = splitted[0] + "-" + interface
        return ".".join(splitted)

    gk = get_api_client()
    network_addresses = [_to_network_address(n) for n in nodes]
    logger.debug(network_addresses)
    gk.sites[site].vlans[str(vlan_id)].nodes.submit(network_addresses)


def get_api_username():
    """Return username of client

    Returns:
        client's username
    """
    gk = get_api_client()
    username = gk.username
    # Anonymous connections happen on g5k frontend
    # In this case we default to the user set in the environment
    if username is None:
        username = os.environ.get("USER")
    return username


@ring.disk(storage)
def get_all_sites_obj():
    """Return the list of the sites.

    Returns:
       list of python-grid5000 sites
    """
    gk = get_api_client()
    sites = gk.sites.list()
    return sites


@ring.disk(storage)
def get_site_obj(site):
    """Get a single site.

    Returns:
        the python-grid5000 site
    """
    gk = get_api_client()
    return gk.sites[site]


@ring.disk(storage)
def clusters_sites_obj(clusters):
    """Get all the corresponding sites of the passed clusters.

    Args:
        clusters(list): list of string uid of sites (e.g 'rennes')

    Return:
        dict corresponding to the mapping cluster uid to python-grid5000 site
    """
    result = {}
    all_clusters = get_all_clusters_sites()
    clusters_sites = {c: s for (c, s) in all_clusters.items() if c in clusters}
    for cluster, site in clusters_sites.items():

        # here we want the site python-grid5000 site object
        result.update({cluster: get_site_obj(site)})
    return result


@ring.disk(storage)
def get_all_clusters_sites():
    """Get all the cluster of all the sites.

    Returns:
        dict corresponding to the mapping cluster uid to python-grid5000 site
    """
    result = {}
    gk = get_api_client()
    sites = gk.sites.list()
    for site in sites:
        clusters = site.clusters.list()
        result.update({c.uid: site.uid for c in clusters})
    return result


def get_clusters_sites(clusters):
    """Get the corresponding sites of given clusters.

    Args:
        clusters(list): list of the clusters (str)

    Returns:
        dict of corresponding to the mapping cluster -> site
    """
    clusters_sites = get_all_clusters_sites()
    return {c: clusters_sites[c] for c in clusters}


def get_cluster_site(cluster):
    """Get the site of a given cluster.

    Args:
        cluster(str): a Grid'5000 cluster

    Returns:
        The corresponding site(str)
    """
    match = get_clusters_sites([cluster])
    return match[cluster]


@ring.disk(storage)
def get_nodes(cluster):
    """Get all the nodes of a given cluster.

    Args:
        cluster(string): uid of the cluster (e.g 'rennes')
    """
    gk = get_api_client()
    site = get_cluster_site(cluster)
    return gk.sites[site].clusters[cluster].nodes.list()


@ring.disk(storage)
def get_node(site, cluster, uid) -> Node:
    gk = get_api_client()
    return gk.sites[site].clusters[cluster].nodes[uid]


def get_nics(cluster):
    """Get the network cards information

    Args:
        cluster(str): Grid'5000 cluster name

    Returns:
        dict of nic information
    """
    nodes = get_nodes(cluster)
    nics = nodes[0].network_adapters
    return nics


def get_cluster_interfaces(cluster, extra_cond=lambda nic: True):
    """Get the network interfaces names corresponding to a criteria.

    Note that the cluster is passed (not the individual node names), thus it is
    assumed that all nodes in a cluster have the same interface names same
    configuration. In addition to ``extra_cond``, only the mountable and
    Ehernet interfaces are returned.

    Args:
        cluster(str): the cluster to consider
        extra_cond(lambda): boolean lambda that takes the nic(dict) as
            parameter
    """
    nics = get_nics(cluster)
    # NOTE(msimonin): Since 05/18 nics on g5k nodes have predictable names but
    # the api description keep the legacy name (device key) and the new
    # predictable name (key name).  The legacy names is still used for api
    # request to the vlan endpoint This should be fixed in
    # https://intranet.grid5000.fr/bugzilla/show_bug.cgi?id=9272
    # When its fixed we should be able to only use the new predictable name.
    nics = [
        (nic["device"], nic["name"])
        for nic in nics
        if nic["mountable"]
        and nic["interface"] == "Ethernet"
        and not nic["management"]
        and extra_cond(nic)
    ]
    nics = sorted(nics)
    return nics


def get_clusters_interfaces(clusters, extra_cond=lambda nic: True):
    """Returns for each cluster the available cluster interfaces

    Args:
        clusters (str): list of the clusters
        extra_cond (lambda): extra predicate to filter network card retrieved
    from the API. E.g lambda nic: not nic['mounted'] will retrieve all the
    usable network cards that are not mounted by default.

    Returns:
        dict of cluster with their associated nic names

    Examples:
        .. code-block:: python

            # pseudo code
            actual = get_clusters_interfaces(["paravance"])
            expected = {"paravance": ["eth0", "eth1"]}
            assertDictEquals(expected, actual)
    """

    interfaces = {}
    for cluster in clusters:
        nics = get_cluster_interfaces(cluster, extra_cond=extra_cond)
        interfaces.setdefault(cluster, nics)

    return interfaces


def can_start_on_cluster(
    nodes_status: Dict, number: int, exact_nodes: List[str], start: int, walltime: int
) -> bool:
    """Check if #nodes can be started on a given cluster.

    This is intended to give a good enough approximation.
    This can be use to prefiltered possible reservation dates before submitting
    them on oar.

    Args:
        nodes_status: a dictionnary with all the status of the nodes as
            returned by the api (cluster status endpoint)
        number: number of node in the demand
        exact_nodes: the list of the fqdn of the machines to get
        start: start time of the job
        walltime: walltime of the job

    Returns
        True iff the job can start
    """
    candidates = []
    # node is the uid, e.g: paranoia-8.rennes.grid5000.fr
    for node, status in nodes_status.items():
        reservations = status.get("reservations", [])
        # we search for the overlapping reservations
        overlapping_reservations = []
        for reservation in reservations:
            queue = reservation.get("queue")
            if queue == "besteffort":
                # ignoring any besteffort reservation
                continue
            r_start = reservation.get("started_at", reservation.get("scheduled_at"))
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
    if len(candidates) >= number and set(exact_nodes).issubset(candidates):
        return True
    return False


def _do_synchronise_jobs(walltime, machines, force=False):
    """This returns a common reservation date for all the jobs.

    This reservation date is really only a hint and will be supplied to each
    oar server. Without this *common* reservation_date, one oar server can
    decide to postpone the start of the job while the other are already
    running. But this doens't prevent the start of a job on one site to drift
    (e.g because the machines need to be restarted.) But this shouldn't exceed
    few minutes.
    To address https://gitlab.inria.fr/discovery/enoslib/-/issues/104 we add
    a force option. Indeed machines can come from different job_types (and
    synchronisation is mandatory in this case even for nodes on the same
    site).
    """
    offset = SYNCHRONISATION_OFFSET
    start = time.time() + offset
    _t = walltime.split(":")
    if len(_t) != 3:
        raise EnosG5kWalltimeFormatError()
    _walltime = int(_t[0]) * 3600 + int(_t[1]) * 60 + int(_t[2])

    # Compute the demand for each cluster
    demands = defaultdict(int)
    # Keeps track of
    exact_nodes = defaultdict(list)
    for machine in machines:
        cluster = machine.cluster
        number, exact = machine.get_demands()
        demands[cluster] += number
        exact_nodes[cluster].extend(exact)

    # Early leave if only one cluster is there (and not force set)
    if not force and len(list(demands.keys())) <= 1:
        logger.debug("Only one cluster detected: no synchronisation needed")
        return None

    clusters = clusters_sites_obj(list(demands.keys()))

    # Early leave if only one site is concerned (and not force set
    sites = set(list(clusters.values()))
    if not force and len(sites) <= 1:
        logger.debug("Only one site detected: no synchronisation needed")
        return None

    # Test the proposed reservation_date
    ko = False
    for cluster, nodes in demands.items():
        cluster_status = clusters[cluster].status.list()
        ko = ko or not can_start_on_cluster(
            cluster_status.nodes, nodes, exact_nodes[cluster], start, _walltime
        )
        if ko:
            break
    if not ko:
        # The proposed reservation_date fits
        logger.info("Reservation_date=%s (%s)" % (_date2h(start), sites))
        return start

    raise EnosG5kSynchronisationError(sites)


@ring.disk(storage)
def get_dns(site):
    site_info = get_site_obj(site)
    return site_info.servers["dns"].network_adapters["default"]["ip"]


@ring.disk(storage)
def get_subnet_gateway(site):
    site_info = get_site_obj(site)
    return site_info.g5ksubnet["gateway"]


@ring.disk(storage)
def get_vlans(site):
    site_info = get_site_obj(site)
    return site_info.kavlans


@ring.disk(storage)
def get_ipv6(site):
    site_info = get_site_obj(site)
    return site_info.ipv6


@ring.disk(storage)
def get_vlan(site, vlan_id) -> Vlan:
    site_info = get_site_obj(site)
    return site_info.vlans[vlan_id]


def deploy(site: str, nodes: List[str], config: Dict) -> Tuple[List[str], List[str]]:
    gk = get_api_client()
    config.update(nodes=nodes)
    deployment = gk.sites[site].deployments.create(config)
    while deployment.status not in ["terminated", "error"]:
        deployment.refresh()
        print("Waiting for the end of deployment [%s]" % deployment.uid)
        time.sleep(10)
    # parse output
    deploy = []
    undeploy = []
    if deployment.status == "terminated":
        deploy = [node for node, v in deployment.result.items() if v["state"] == "OK"]
        undeploy = [node for node, v in deployment.result.items() if v["state"] == "KO"]
    elif deployment.status == "error":
        undeploy = nodes

    return deploy, undeploy


def grid_get_or_create_job(
    job_name,
    walltime,
    reservation_date,
    queue,
    job_type,
    project,
    machines,
    networks,
    wait=True,
):
    jobs = grid_reload_from_name(job_name)
    if len(jobs) == 0:
        jobs = grid_make_reservation(
            job_name,
            walltime,
            reservation_date,
            queue,
            job_type,
            project,
            machines,
            networks,
        )
    if wait:
        wait_for_jobs(jobs)
        return build_resources(jobs)
    return None


def _build_reservation_criteria(machines, networks):
    criteria = {}
    # machines reservations
    # FIXME(msimonin): this should be refactor like this
    # for machine in machines
    #     machine.to_oar_string() ...
    for config in machines:
        # a desc is either given by
        #  a cluster name + a number of nodes
        # or a list of specific servers
        # the (implicit) semantic is that if servers is given cluster and nodes
        # are unused

        # let's start with the servers case
        site, criterion = config.oar()
        if criterion is not None:
            criteria.setdefault(site, []).append(criterion)

    for config in networks:
        site, criterion = config.oar()
        if criterion is not None:
            # in the prod case nothing is generated
            criteria.setdefault(site, []).append(criterion)

    return criteria


def _do_grid_make_reservation(
    criterias, job_name, walltime, reservation_date, queue, job_type, project
):
    job_specs = []
    if isinstance(job_type, str):
        job_type = [job_type]
    for site, criteria in criterias.items():
        resources = "+".join(criteria)
        resources = "%s,walltime=%s" % (resources, walltime)
        job_spec = {
            "name": job_name,
            "types": job_type,
            "resources": resources,
            "command": "sleep 31536000",
            "queue": queue,
        }
        if project:
            job_spec.update(project=project)
        if reservation_date:
            job_spec.update(reservation=reservation_date)
        job_specs.append((site, job_spec))

    jobs = submit_jobs(job_specs)
    return jobs


def grid_make_reservation(
    job_name, walltime, reservation_date, queue, job_type, project, machines, networks
):
    if not reservation_date:
        # First check if synchronisation is required
        reservation_date = _do_synchronise_jobs(walltime, machines)

    # Build the OAR criteria
    criteria = _build_reservation_criteria(machines, networks)

    # Submit them
    jobs = _do_grid_make_reservation(
        criteria, job_name, walltime, reservation_date, queue, job_type, project
    )

    return jobs
