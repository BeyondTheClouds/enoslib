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

    A driver is responsible for interacting with Grid5000 to get resources and
    destroy them. These action can be done using oar (single site), oargrid
    (multisite) or the REST API.

    TODO: Turn this into a singleton
    """

    __metaclass__ = ABCMeta

    def __init__(self):
        # underlying jobs
        self._jobs = []

    @property
    def jobs(self):
        # make sure jobs is reloaded (if any) and return them
        if not self._jobs:
            self._jobs = self.get_jobs()
        return self._jobs

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
    Thus, one must pass a list of jobs here (one for each site).
    Note that they can be created using oargrid manually.

    - reserve will create or reload the job resources from all the (site, id)s
    - destroy will destroy the oargrid job given all the (site, id)s
    """

    def __init__(self, oargrid_jobids):
        super().__init__()
        self.oargrid_jobids = oargrid_jobids

    def reserve(self):
        self._jobs = grid_reload_from_ids(self.oargrid_jobids)

    def destroy(self, wait=False):
        grid_destroy_from_ids(self.oargrid_jobids, wait=wait)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)

    def get_jobs(self) -> List[Job]:
        return grid_reload_jobs_from_ids(self.oargrid_jobids)


class OargridDynamicDriver(Driver):
    """
    Use this driver when a new oargrid job must be created

    Since enoslib 3 we deprecated the use of oargridsub. Thus we need to keep a
    way to recover the job running on each site corresponding to the current
    deployment. This is done using the job name.
    """

    def __init__(self, configuration):

        super().__init__()
        self.job_name = configuration.job_name
        self.walltime = configuration.walltime
        self.job_type = configuration.job_type
        self.monitor = configuration.monitor
        self.reservation_date = configuration.reservation
        self.project = configuration.project
        # NOTE(msimonin): some time ago asimonet proposes to auto-detect
        # the queues and it was quiet convenient
        # see https://github.com/BeyondTheClouds/enos/pull/62
        self.queue = configuration.queue
        self.machines = configuration.machines
        self.networks = configuration.networks

        # Used to restrict the driver when we scan the jobs
        self.sites = configuration.sites

    def reserve(self):
        self._jobs = grid_get_or_create_job(
            self.job_name,
            self.walltime,
            self.reservation_date,
            self.queue,
            self.job_type,
            self.monitor,
            self.project,
            self.machines,
            self.networks,
            restrict_to=self.sites,
        )

    def destroy(self, wait=False):
        grid_destroy_from_name(self.job_name, wait=wait, restrict_to=self.sites)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)

    def get_jobs(self) -> List[Job]:
        return grid_reload_jobs_from_name(self.job_name, restrict_to=self.sites)


def get_driver(
    configuration: Configuration,
) -> Union[OargridDynamicDriver, OargridStaticDriver]:
    """Build an instance of the driver to interact with G5K"""
    oargrid_jobids = configuration.oargrid_jobids

    if oargrid_jobids:
        logger.debug("Loading the OargridStaticDriver")
        return OargridStaticDriver(oargrid_jobids)
    else:
        return OargridDynamicDriver(configuration)
