# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Union
from enoslib.infra.enos_g5k.configuration import Configuration
import logging

from enoslib.infra.enos_g5k.g5k_api_utils import (
    get_api_username,
    grid_deploy,
    grid_destroy_from_name,
    grid_destroy_from_ids,
    grid_get_or_create_job,
    grid_reload_from_ids,
)

logger = logging.getLogger(__name__)


class Driver:
    """Base class for all g5k drivers.

    A driver is reponsible for interacting with Grid5000 to get resources and
    destroy them. These action can be done using oar (single site), oargrid
    (multisite) or the REST API.

    TODO: Turn this into a singleton
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def reserve(self, wait=True):
        pass

    @abstractmethod
    def destroy(self):
        pass

    @abstractmethod
    def deploy(self, site, nodes, force_deploy, options):
        pass

    def get_user(self):
        return get_api_username()


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
        self.oargrid_jobids = oargrid_jobids

    def reserve(self, wait=True):
        nodes, networks = grid_reload_from_ids(self.oargrid_jobids)
        return nodes, networks

    def destroy(self):
        grid_destroy_from_ids(self.oargrid_jobids)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)


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
        project,
        reservation_date,
        queue,
        machines,
        networks,
    ):
        self.job_name = job_name
        self.walltime = walltime
        self.job_type = job_type
        self.project = project
        self.reservation_date = reservation_date
        self.queue = queue
        self.machines = machines
        self.networks = networks

    def reserve(self, wait=True):
        return grid_get_or_create_job(
            self.job_name,
            self.walltime,
            self.reservation_date,
            self.queue,
            self.job_type,
            self.project,
            self.machines,
            self.networks,
            wait=wait,
        )

    def destroy(self):
        grid_destroy_from_name(self.job_name)

    def deploy(self, site, nodes, options):
        return grid_deploy(site, nodes, options)


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
            project,
            reservation_date,
            queue,
            machines,
            networks,
        )
