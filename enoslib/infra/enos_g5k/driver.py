# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
import logging

from enoslib.infra.enos_g5k.utils import (grid_deploy,
                                          grid_get_or_create_job,
                                          grid_destroy_from_name,
                                          grid_reload_from_ids,
                                          grid_destroy_from_ids)
from enoslib.infra.enos_g5k.constants import (DEFAULT_JOB_NAME,
                                              DEFAULT_WALLTIME,
                                              JOB_TYPE_DEPLOY)


logger = logging.getLogger(__name__)


def get_driver(configuration, gk):
    """Build an instance of the driver to interact with G5K
    """
    resources = configuration["resources"]
    machines = resources["machines"]
    networks = resources["networks"]
    oargrid_jobids = configuration.get("oargrid_jobids")

    if oargrid_jobids:
        logger.debug("Loading the OargridStaticDriver")
        return OargridStaticDriver(gk, oargrid_jobids)
    else:
        job_name = configuration.get("job_name", DEFAULT_JOB_NAME)
        walltime = configuration.get("walltime", DEFAULT_WALLTIME)
        job_type = configuration.get("job_type", JOB_TYPE_DEPLOY)
        reservation_date = configuration.get("reservation", False)
        # NOTE(msimonin): some time ago asimonet proposes to auto-detect
        # the queues and it was quiet convenient
        # see https://github.com/BeyondTheClouds/enos/pull/62
        queue = configuration.get("queue", None)
        logger.debug("Loading the OargridDynamicDriver")

        return OargridDynamicDriver(
            gk,
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

    @abstractmethod
    def deploy(self, site, nodes, force_deploy, options):
        pass


class OargridStaticDriver(Driver):
    """
    Use this driver when a list of oar job ids and sites are given

    Since enoslib 3 we deprecated the use of oargridsub.
    Thus one must pass a list of jobs here (one for each site).
    Note that they can be created using oargrid manually.

    - reserve will create or reload the job resources from all the (site, id)s
    - destroy will destroy the oargrid job given all the (site, id)s
    """
    def __init__(self, gk, oargrid_jobids):
        self.gk = gk
        self.oargrid_jobids = oargrid_jobids

    def reserve(self):
        nodes, networks = grid_reload_from_ids(self.gk, self.oargrid_jobids)
        return nodes, networks

    def destroy(self):
        grid_destroy_from_ids(self.oargrid_jobids)

    def deploy(self, site, nodes, force_deploy, options):
        return grid_deploy(self.gk, site, nodes, force_deploy, options)


class OargridDynamicDriver(Driver):
    """
    Use this driver when a new oargrid job must be created

    Since enoslib 3 we deprecated the use of oargridsub. Thus we need to keep a
    way to recover the job running on each site corresponding to the current
    deployment. This is done using the job name.
    """
    def __init__(self,
                 gk,
                 job_name,
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
        self.gk = gk

    def reserve(self):
        nodes, networks = grid_get_or_create_job(self.gk,
                                                 self.job_name,
                                                 self.walltime,
                                                 self.reservation_date,
                                                 self.queue,
                                                 self.job_type,
                                                 self.machines,
                                                 self.networks)

        return nodes, networks

    def destroy(self):
        grid_destroy_from_name(self.gk, self.job_name)

    def deploy(self, site, nodes, force_deploy, options):
        return grid_deploy(self.gk, site, nodes, force_deploy, options)
