# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from enoslib.infra.enos_g5k.utils import (grid_get_or_create_job,
                                          grid_reload_from_id,
                                          grid_destroy_from_name,
                                          grid_destroy_from_id,
                                          oar_reload_from_id,
                                          oar_destroy_from_id)
from enoslib.infra.enos_g5k.constants import (JOB_NAME, WALLTIME,
                                              JOB_TYPE_DEPLOY)
import logging

logger = logging.getLogger(__name__)


def get_driver(configuration):
    """Build an instance of the driver to interact with G5K
    """
    resources = configuration["resources"]
    machines = resources["machines"]
    networks = resources["networks"]
    oargrid_jobid = configuration.get("oargrid_jobid")
    oar_jobid = configuration.get("oar_jobid")
    oar_site = configuration.get("oar_site")
    if oargrid_jobid:
        logger.debug("Loading the OargridStaticDriver")
        return OargridStaticDriver(oargrid_jobid)
    elif oar_jobid and oar_site:
        logger.debug("Loading the OarStaticDriver")
        return OarStaticDriver(oar_jobid, oar_site)
    else:
        job_name = configuration.get("job_name", JOB_NAME)
        walltime = configuration.get("walltime", WALLTIME)
        job_type = configuration.get("job_type", JOB_TYPE_DEPLOY)
        reservation_date = configuration.get("reservation", False)
        # NOTE(msimonin): some time ago asimonet proposes to auto-detect
        # the queues and it was quiet convenient
        # see https://github.com/BeyondTheClouds/enos/pull/62
        queue = configuration.get("queue", None)
        logger.debug("Loading the OargridDynamicDriver")
        return OargridDynamicDriver(
            job_name,
            walltime,
            job_type,
            reservation_date,
            queue,
            machines,
            networks
        )


class Driver:
    """Base class for all g5k drivers.

    A driver is reponsible for interacting with Grid5000 to get resources and
    destroy them. These action can be done using oar (single site), oargrid
    (multisite) or the REST API.

    TODO: Turn this into a singleton
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def reserve(self):
        pass

    @abstractmethod
    def destroy(self):
        pass


class OargridStaticDriver(Driver):
    """
    Use this driver when a oargrid job id is given.

    - reserve will reload the job resources from the job id
    - destroy will destroy the oargrid job given its id
    """
    def __init__(self, oargrid_jobid):
        self.oargrid_jobid = int(oargrid_jobid)

    def reserve(self):
        nodes, vlans, subnets = grid_reload_from_id(self.oargrid_jobid)
        return nodes, vlans, subnets

    def destroy(self):
        grid_destroy_from_id(self.oargrid_jobid)


class OargridDynamicDriver(Driver):
    """
    Use this driver when a new oargrid job must be created

    - reserve will create or reload the job resources from the job name
    - destroy will destroy the oargrid job given its name
    """
    def __init__(self, job_name,
                 walltime,
                 job_type,
                 reservation_date,
                 queue,
                 machines,
                 networks):
        self.job_name = job_name
        self.walltime = walltime
        self.job_type = job_type
        self.reservation_date = reservation_date
        self.queue = queue
        self.machines = machines
        self.networks = networks

    def reserve(self):
        gridjob = grid_get_or_create_job(self.job_name,
                                         self.walltime,
                                         self.reservation_date,
                                         self.queue,
                                         self.job_type,
                                         self.machines,
                                         self.networks)

        nodes, vlans, subnets = grid_reload_from_id(gridjob)
        return nodes, vlans, subnets

    def destroy(self):
        grid_destroy_from_name(self.job_name)


class OarStaticDriver(Driver):
    """
    Use this driver when a oar job id is given.

    - reserve will reload the job resources from the job id
    - destroy will destroy the oargrid job given its id
    """
    def __init__(self, oar_jobid, oar_site):
        self.oar_jobid = int(oar_jobid)
        self.oar_site = oar_site

    def reserve(self):
        nodes, vlans, subnets = oar_reload_from_id(self.oar_jobid,
                                                   self.oar_site)
        return nodes, vlans, subnets

    def destroy(self):
        oar_destroy_from_id(self.oar_jobid,
                            self.oar_site)
