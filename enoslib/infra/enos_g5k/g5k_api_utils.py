"""
This module is composed of helpers functions to deal with the Grid'5000 REST
API.

It wraps the python-grid5000 library to provide some usual routines to interact
with the platform.
"""

from collections import defaultdict, namedtuple
from datetime import datetime, timezone
from functools import lru_cache

import re
from grid5000.objects import Job, Node, Vlan
import os
import time
import threading
from typing import Dict, Iterable, List, MutableMapping, Optional, Tuple
from pathlib import Path

import pytz

from .error import (
    EnosG5kDuplicateJobsError,
    EnosG5kWalltimeFormatError,
)
from .constants import (
    KAVLAN_GLOBAL,
    KAVLAN_IDS,
    KAVLAN_LOCAL,
    KAVLAN,
    KAVLAN_LOCAL_IDS,
    PROD_VLAN_ID,
    NATURE_PROD,
    MAX_DEPLOY,
)
from enoslib.log import getLogger
from enoslib.infra.utils import _date2h

from grid5000 import Grid5000

from grid5000.exceptions import Grid5000DeleteError


logger = getLogger(__name__, ["G5k"])


_api_lock = threading.Lock()
# Keep track of the api client
_api_client = None


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


# Lightweight representation of a network returned by OAR
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


def grid_reload_jobs_from_ids(oargrid_jobids):
    """Reload jobs of Grid'5000 from their ids

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


def grid_reload_jobs_from_name(job_name, restrict_to: Optional[List[str]] = None):
    """Reload all running or pending jobs of Grid'5000 with a given name.

    By default, all the sites will be searched for jobs with the name
    ``job_name``. Using EnOSlib there can be only one job per site with name
    ``job_name``.

    Note that it honors the ``exluded_sites`` attribute of the client so the
    scan can be reduced.

    Args:
        job_name (str): the job name
        restrict_to: restrict the action to these sites only.
            If None is passed, no restriction applies and the action will be
            taken on all possible sites

    Returns:
        The list of the python-grid5000 jobs retrieved.

    Raises:
        EnosG5kDuplicateJobsError: if there's several jobs with the same name
            on a site.
    """
    gk = get_api_client()
    sites = get_all_sites_obj()
    if restrict_to is None:
        restrict_to = [s.uid for s in sites]
    jobs = []
    for site in [
        s for s in sites if s.uid not in gk.excluded_site and s.uid in restrict_to
    ]:
        logger.debug(f"Reloading {job_name} from {site.uid}")
        _jobs = site.jobs.list(
            name=job_name, state="waiting,launching,running", user=get_api_username()
        )
        if len(_jobs) == 1:
            logger.info(f"Reloading {_jobs[0].uid} from {site.uid}")
            jobs.append(_jobs[0])
        elif len(_jobs) > 1:
            raise EnosG5kDuplicateJobsError(site, job_name)
    # finally refresh them
    # this adds some extra info (assigned_nodes)
    for job in jobs:
        job.refresh()
    return jobs


def grid_reload_from_ids(oargrid_jobids):
    """Reload all running or pending jobs of Grid'5000 from their ids

    Args:
        oargrid_jobids (list): list of ``(site, oar_jobid)`` identifying the
            jobs on each site

    Returns:
        The list of python-grid5000 jobs retrieved
    """
    jobs = grid_reload_jobs_from_ids(oargrid_jobids)
    return jobs


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
        # can have several subnet like this (e.g. when requesting a /16)
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

    logger.debug(f"nodes={nodes}, networks={networks}")
    return nodes, networks


def job_delete(job, wait=False):
    # In the event that a job has already been killed when we try to kill it,
    # we ignore the error raised by Grid5000 to warn us
    try:
        job.delete()
    except Grid5000DeleteError as error:
        search = re.search(
            "This job was already killed",
            format(error),
        )
        if search is None:
            raise error
    if not wait:
        return
    while job.state in ["running", "waiting", "launching"]:
        logger.debug(f"Waiting for the job ({job.site}, {job.uid}) to be killed")
        time.sleep(1)
        job.refresh()
    logger.info(f"Job killed ({job.site}, {job.uid})")


def grid_destroy_from_name(
    job_name, wait=False, restrict_to: Optional[List[str]] = None
):
    """Destroy all the jobs with a given name.

    Args:
        job_name (str): the job name
        wait: True whether we should wait for a status change
        restrict_to: restrict the action to these sites only.
            If None is passed, no restriction applies and the action will be
            taken on all possible sites
    """
    jobs = grid_reload_jobs_from_name(job_name, restrict_to=restrict_to)
    for job in jobs:
        logger.info(f"Killing the job ({job.site}, {job.uid})")
        job_delete(job, wait=wait)


def grid_destroy_from_ids(oargrid_jobids, wait=False):
    """Destroy all the jobs with corresponding ids

    Args:
        oargrid_jobids (list): the ``(site, oar_job_id)`` list of tuple
            identifying the jobs for each site.
        wait: True whether we should wait for a status change
    """
    jobs = grid_reload_from_ids(oargrid_jobids)
    for job in jobs:
        job_delete(job, wait=wait)
        logger.info("Killing the jobs %s" % oargrid_jobids)


def submit_jobs(job_specs):
    """Submit a job

    Args:
        job_specs (dict): The job specification (see Grid'5000 API reference)
    """
    gk = get_api_client()
    jobs = []
    try:
        for site, job_spec in job_specs:
            logger.info(f"Submitting {job_spec} on {site}")
            jobs.append(gk.sites[site].jobs.create(job_spec))
    except Exception as e:
        logger.error("An error occurred during the job submissions")
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
        config(dict): option of the deployment (refer to the Grid'5000 API
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


def get_all_sites_obj():
    """Return the list of the sites.

    Returns:
       list of python-grid5000 sites
    """
    gk = get_api_client()
    sites = gk.sites.list()
    return sites


def get_site_obj(site):
    """Get a single site.

    Returns:
        the python-grid5000 site
    """
    gk = get_api_client()
    return gk.sites[site]


def clusters_sites_obj(clusters: Iterable) -> Dict:
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


@lru_cache(maxsize=32)
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
    logger.debug(result)
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


def get_nodes(cluster):
    """Get all the nodes of a given cluster.

    Args:
        cluster(string): uid of the cluster (e.g 'rennes')
    """
    gk = get_api_client()
    site = get_cluster_site(cluster)
    return gk.sites[site].clusters[cluster].nodes.list()


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
    from the API. E.g. lambda nic: not nic['mounted'] will retrieve all the
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
    nodes_status: Dict, number: int, exact_nodes: List[str], start: float, walltime: int
) -> bool:
    """Check if #nodes can be started on a given cluster.

    This is intended to give a good enough approximation.
    This can be used to prefiltered possible reservation dates before submitting
    them on oar.

    Args:
        nodes_status: a dictionary with all the status of the nodes as
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
            _intersect = min(float(r_end), start + walltime) - max(
                float(r_start), start
            )
            if _intersect > 0:
                overlapping_reservations.append(reservation)
        if len(overlapping_reservations) == 0:
            # this node can be accounted for a potential reservation
            candidates.append(node)
    if len(candidates) >= number and set(exact_nodes).issubset(candidates):
        return True
    return False


def _test_slot(
    start: int,
    walltime: str,
    machines: Dict,
    clusters_status: Dict,
) -> bool:
    """
    This function test if it is possible at a specified start time to
    make a reservation using the machines specified in machines dictionary
    To do so it takes clusters_status as an entry, which is the result of api calls
    to get the status of the corresponding clusters

    Returns:
        The return value follows this semantic:
            - False: the proposed slot isn't available for the reservation
            - True: the proposed start date seems to be available
                (at the time of probing the API)
    """
    tz = pytz.timezone("Europe/Paris")
    date = datetime.fromtimestamp(start, timezone.utc)
    start = int(date.astimezone(tz=tz).timestamp())
    _t = walltime.split(":")
    if len(_t) != 3:
        raise EnosG5kWalltimeFormatError()
    _walltime = int(_t[0]) * 3600 + int(_t[1]) * 60 + int(_t[2])

    # Compute the demand for each cluster
    demands: MutableMapping[str, int] = defaultdict(int)
    # Keeps track of
    exact_nodes = defaultdict(list)
    for machine in machines:
        cluster = machine.cluster
        number, exact = machine.get_demands()
        demands[cluster] += number
        exact_nodes[cluster].extend(exact)

    ko = False

    for cluster, nodes in demands.items():
        ko = ko or not can_start_on_cluster(
            clusters_status[cluster].nodes,
            nodes,
            exact_nodes[cluster],
            start,
            _walltime,
        )
        if ko:
            return False
    if not ko:
        # The proposed reservation_date fits
        return True
    return False


@lru_cache(maxsize=32)
def get_dns(site):
    site_info = get_site_obj(site)
    return site_info.servers["dns"].network_adapters["default"]["ip"]


@lru_cache(maxsize=32)
def get_subnet_gateway(site):
    site_info = get_site_obj(site)
    return site_info.g5ksubnet["gateway"]


@lru_cache(maxsize=32)
def get_vlans(site):
    site_info = get_site_obj(site)
    return site_info.kavlans


@lru_cache(maxsize=32)
def get_ipv6(site):
    site_info = get_site_obj(site)
    return site_info.ipv6


@lru_cache(maxsize=32)
def get_vlan(site, vlan_id) -> Vlan:
    site_info = get_site_obj(site)
    return site_info.vlans[vlan_id]


def get_clusters_status(clusters: Iterable[str]):
    """Get the status of the clusters (current and future reservations)."""
    # mapping cluster -> site
    clusters_sites: Dict = clusters_sites_obj(clusters)
    clusters_status = {}
    for cluster in clusters_sites:
        clusters_status[cluster] = (
            clusters_sites[cluster].clusters[cluster].status.list()
        )
    return clusters_status


def deploy(site: str, nodes: List[str], config: Dict) -> Tuple[List[str], List[str]]:
    gk = get_api_client()
    config.update(nodes=nodes)
    deployment = gk.sites[site].deployments.create(config)
    while deployment.status not in ["terminated", "error"]:
        deployment.refresh()
        logger.info("Waiting for the end of deployment [%s]" % deployment.uid)
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
    monitor,
    project,
    machines,
    networks,
    wait=True,
    restrict_to: Optional[List[str]] = None,
):
    jobs = grid_reload_jobs_from_name(job_name, restrict_to=restrict_to)
    if len(jobs) == 0:
        jobs = grid_make_reservation(
            job_name,
            walltime,
            reservation_date,
            queue,
            job_type,
            monitor,
            project,
            machines,
            networks,
        )
    return jobs


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
    criterias, job_name, walltime, reservation_date, queue, job_type, monitor, project
):
    job_specs = []
    if isinstance(job_type, str):
        job_type = [job_type]
    if monitor is not None:
        job_type.append(f"monitor={monitor}")
    for site, criteria in criterias.items():
        resources = "+".join(criteria)
        resources = f"{resources},walltime={walltime}"
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
    job_name,
    walltime,
    reservation_date,
    queue,
    job_type,
    monitor,
    project,
    machines,
    networks,
):
    # Build the OAR criteria
    criteria = _build_reservation_criteria(machines, networks)

    # Submit them
    jobs = _do_grid_make_reservation(
        criteria,
        job_name,
        walltime,
        reservation_date,
        queue,
        job_type,
        monitor,
        project,
    )

    return jobs


def enable_home_for_job(job: Job, ips: List[str]):
    """Enable access to home dir from ips.

    This allows to mount the home dir corresponding to the site of job
    from any of the ips provided.


    Examples:

        .. code-block:: python

            roles, networks = provider.init()
            # get some ips to allow
            ips = [str(ip) for ip in networks["role"][0].network]

            # get the underlying job
            job = provider.jobs[0]
            enable_home_for_job(job, ips)

    For enabling any group storage, please refer to
    :py:func:`~.enable_group_storage`

    Args:
        job: A (running) job.
            home site and access duration will be inferred from
            this job
        ips: list of IPs
            Every machine connecting from one of this IPs will be granted an
            access to the home directory

    """
    username = get_api_username()
    enable_group_storage(job.site, "home", username, ips, job)


def enable_group_storage(
    storage_site: str,
    storage_server: str,
    storage_name: str,
    ips: List[str],
    termination_job: Job,
):
    """Enable access to a group storage from ips.

    Args:
        storage_site: a grid'5000 site.
            Site where the storage is located
        storage_server: a server name
            Storage server where the storage is located (e.g. ~"storage1"~  or
            ~"home"~)
        storage_name: name of the group storage
            The name is the one used to identify a Group Storage (this might be
            your username if you plan to allow your home dir)
        ips: list of ips
            Ips to allow the access from (only IPv4 for now).
        termination_job: a job
            This is used as a termination condition
    """
    gk = get_api_client()
    (
        gk.sites[storage_site]
        .storage[storage_server]
        .access[storage_name]
        .rules.create(
            {
                "ipv4": ips,
                "termination": {
                    "job": termination_job.uid,
                    "site": termination_job.site,
                },
            }
        )
    )
