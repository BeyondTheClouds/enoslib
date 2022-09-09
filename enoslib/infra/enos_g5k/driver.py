from abc import ABCMeta, abstractmethod
from typing import List, Union, Tuple

from grid5000.objects import Job
from enoslib.infra.enos_g5k.configuration import Configuration

from enoslib.infra.enos_g5k.g5k_api_utils import (
    build_resources,
    get_api_username,
    grid_deploy,
    grid_destroy_from_name,
    grid_destroy_from_ids,
    grid_get_or_create_job,
    grid_reload_from_ids,
    grid_reload_jobs_from_ids,
    grid_reload_jobs_from_name,
    wait_for_jobs,
    OarNetwork,
)
from enoslib.log import getLogger

logger = getLogger(__name__, ["G5k"])


class Driver:
    """Base class for all g5k drivers.

    A driver is reponsible for interacting with Grid5000 to get resources and
    destroy them. These action can be done using oar (single site), oargrid
    (multisite) or the REST API.

    TODO: Turn this into a singleton
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        # underlying jobs
        self.jobs = []

    @abstractmethod
    def reserve(self, wait=True):
        pass

    @abstractmethod
    def destroy(self, wait=False):
        pass

    @abstractmethod
    def deploy(self, site, nodes, force_deploy, options):
        pass

    @abstractmethod
    def get_jobs(self):
        pass

    def get_user(self) -> str:
        return get_api_username()

    def wait(self):
        wait_for_jobs(self.jobs)

    def resources(self) -> Tuple[List[str], List[OarNetwork]]:
        return build_resources(self.jobs)


class OargridStaticDriver(Driver):
    """
    Use this driver when a list of oar job ids and sites are given

    Since enoslib 3 we deprecated the use of oargridsub.
    Thus one must pass a list of jobs here (one for each site).
    Note that they can be created using oargrid manually.

    - reserve will create or reload the job resources from all the (site, id)s
    - destroy will destroy the oargrid job given all the (site, id)s
    """

    def __init__(self, oargrid_jobids):
        super().__init__()
        self.oargrid_jobids = oargrid_jobids

    def reserve(self):
        self.jobs = grid_reload_from_ids(self.oargrid_jobids)

    def destroy(self, wait=False):
        grid_destroy_from_ids(self.oargrid_jobids, wait=wait)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)

    def get_jobs(self) -> List[Job]:
        if self.jobs:
            return self.jobs
        else:
            grid_reload_jobs_from_ids(self.oargrid_jobids)


class OargridDynamicDriver(Driver):
    """
    Use this driver when a new oargrid job must be created

    Since enoslib 3 we deprecated the use of oargridsub. Thus we need to keep a
    way to recover the job running on each site corresponding to the current
    deployment. This is done using the job name.
    """

    def __init__(
        self,
        job_name,
        walltime,
        job_type,
        monitor,
        project,
        reservation_date,
        queue,
        machines,
        networks,
    ):

        super().__init__()
        self.job_name = job_name
        self.walltime = walltime
        self.job_type = job_type
        self.monitor = monitor
        self.project = project
        self.reservation_date = reservation_date
        self.queue = queue
        self.machines = machines
        self.networks = networks

    def reserve(self):
        self.jobs = grid_get_or_create_job(
            self.job_name,
            self.walltime,
            self.reservation_date,
            self.queue,
            self.job_type,
            self.monitor,
            self.project,
            self.machines,
            self.networks,
        )

    def destroy(self, wait=False):
        grid_destroy_from_name(self.job_name, wait=wait)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)

    def get_jobs(self) -> List[Job]:
        if self.jobs:
            return self.jobs
        else:
            return grid_reload_jobs_from_name(self.job_name)


def get_driver(
    configuration: Configuration,
) -> Union[OargridDynamicDriver, OargridStaticDriver]:
    """Build an instance of the driver to interact with G5K"""
    machines = configuration.machines
    networks = configuration.networks
    oargrid_jobids = configuration.oargrid_jobids
    project = configuration.project

    if oargrid_jobids:
        logger.debug("Loading the OargridStaticDriver")
        return OargridStaticDriver(oargrid_jobids)
    else:
        job_name = configuration.job_name
        walltime = configuration.walltime
        job_type = configuration.job_type
        monitor = configuration.monitor
        reservation_date = configuration.reservation
        # NOTE(msimonin): some time ago asimonet proposes to auto-detect
        # the queues and it was quiet convenient
        # see https://github.com/BeyondTheClouds/enos/pull/62
        queue = configuration.queue
        logger.debug("Loading the OargridDynamicDriver")

        return OargridDynamicDriver(
            job_name,
            walltime,
            job_type,
            monitor,
            project,
            reservation_date,
            queue,
            machines,
            networks,
        )
