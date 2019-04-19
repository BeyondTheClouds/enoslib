"""
This module is composed of helpers functions to deal with the Grid'5000 REST
API.

It wraps the python-grid5000 library to provide some usual routines to interact
with the platform.
"""

from collections import defaultdict
import functools
import logging
import os
import pickle
import time
import threading

from .error import EnosG5kDuplicateJobsError, EnosG5kSynchronisationError
from .constants import SYNCHRONISATION_OFFSET, DEFAULT_SSH_KEYFILE

from grid5000 import Grid5000


logger = logging.getLogger(__name__)


_api_lock = threading.Lock()
# Keep track of the api client
_api_client = None

# Poor man's cache (for now)
_cache_lock = threading.RLock()
cache = {}


def cached(f):
    """Decorator for caching/retrieving api calls request.

    Many calls to the API are getter on static parts (e.g site of a given
    cluster name won't change). By caching some responses we can avoid
    hammering the API server.
    """
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        with _cache_lock:
            identifier = (f.__name__,  args, kwargs)
            key = pickle.dumps(identifier)
            value = cache.get(key)
            if value is not None:
                logger.debug("HIT for %s -> %s" % (str(identifier), value))
            else:
                logger.debug("MISS for %s" % str(identifier))
                value = f(*args, **kwargs)
                cache[key] = value
            return value
    return wrapped


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


def get_api_client():
    """Gets the reference to the API cient (singleton)."""
    with _api_lock:
        global _api_client
        if not _api_client:
            conf_file = os.path.join(os.environ.get("HOME"),
                                     ".python-grid5000.yaml")
            _api_client = Client.from_yaml(conf_file)

        return _api_client


def _date2h(timestamp):
    t = time.strftime("%Y-%m-%d %H:%M:%S",
                      time.localtime(timestamp))
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
        _jobs = site.jobs.list(name=job_name,
                               state="waiting,launching,running")
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
    return jobs


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
            identifying the jobs for each site. """
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
        raise(e)

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
                logger.info("Waiting for %s on %s [%s]" % (job.uid,
                                                           job.site,
                                                           _date2h(scheduled)))
            all_running = all_running and job.state == "running"
            if job.state == "error":
                raise Exception("The job %s is in error state" % job)
    logger.info("All jobs are Running !")


def grid_deploy(site, nodes, options):
    """Deploy and wait for the deployment to be finished.

    Args:
        site(str): the site
        nodes(list): list of nodes (str) to depoy
        options(dict): option of the deployment (refer to the Grid'5000 API
            Specifications)

    Returns:
        tuple of deployed(list), undeployed(list) nodes.
    """
    gk = get_api_client()
    environment = options.pop("env_name")
    options.update(environment=environment)
    options.update(nodes=nodes)
    key_path = DEFAULT_SSH_KEYFILE
    options.update(key=key_path.read_text())
    logger.info("Deploying %s with options %s" % (nodes, options))
    deployment = gk.sites[site].deployments.create(options)
    while deployment.status not in ["terminated", "error"]:
        deployment.refresh()
        print("Waiting for the end of deployment [%s]" % deployment.uid)
        time.sleep(10)

    deploy = []
    undeploy = []
    if deployment.status == "terminated":
        deploy = [node for node, v in deployment.result.items()
                  if v["state"] == "OK"]
        undeploy = [node for node, v in deployment.result.items()
                    if v["state"] == "KO"]
    elif deployment.status == "error":
        undeploy = nodes
    return deploy, undeploy


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
        splitted = host.split('.')
        splitted[0] = splitted[0] + "-" + interface
        return ".".join(splitted)

    gk = get_api_client()
    network_addresses = [_to_network_address(n) for n in nodes]
    gk.sites[site].vlans[str(vlan_id)].submit({"nodes": network_addresses})


@cached
def get_all_sites_obj():
    """Return the list of the sites.

    Returns:
       list of python-grid5000 sites
    """
    gk = get_api_client()
    sites = gk.sites.list()
    return sites


@cached
def get_site_obj(site):
    """Get a single site.

    Returns:
        the python-grid5000 site
    """
    gk = get_api_client()
    return gk.sites[site]


@cached
def clusters_sites_obj(clusters):
    """Get all the corresponding sites of the passed clusters.

    Args:
        clusters(list): list of string uid of sites (e.g 'rennes')

    Return:
        dict corresponding to the mapping cluster uid to python-grid5000 site
    """
    result = {}
    all_clusters = get_all_clusters_sites()
    clusters_sites = {c: s for (c, s) in all_clusters.items()
                        if c in clusters}
    for cluster, site in clusters_sites.items():

        # here we want the site python-grid5000 site object
        result.update({cluster: get_site_obj(site)})
    return result


@cached
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


@cached
def get_nodes(cluster):
    """Get all the nodes of a given cluster.

    Args:
        cluster(string): uid of the cluster (e.g 'rennes')
    """
    gk = get_api_client()
    site = get_cluster_site(cluster)
    return gk.sites[site].clusters[cluster].nodes.list()


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
    nics = [(nic['device'], nic['name']) for nic in nics
            if nic['mountable']
            and nic['interface'] == 'Ethernet'
            and not nic['management']
            and extra_cond(nic)]
    nics = sorted(nics)
    return nics


def get_clusters_interfaces(clusters, extra_cond=lambda nic: True):
    """ Returns for each cluster the available cluster interfaces

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


def _do_synchronise_jobs(walltime, machines):
    """ This returns a common reservation date for all the jobs.

    This reservation date is really only a hint and will be supplied to each
    oar server. Without this *common* reservation_date, one oar server can
    decide to postpone the start of the job while the other are already
    running. But this doens't prevent the start of a job on one site to drift
    (e.g because the machines need to be restarted.) But this shouldn't exceed
    few minutes.
    """
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

    clusters = clusters_sites_obj(list(demands.keys()))

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

    if start is None:
        raise EnosG5kSynchronisationError(sites)
