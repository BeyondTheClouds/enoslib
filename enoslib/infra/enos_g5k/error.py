# -*- coding: utf-8 -*-
from enoslib.errors import EnosError


class DeployError(Exception):
    pass


class MissingNetworkError(DeployError):
    def __init__(self, site, n_type):
        self.site = site
        self.n_type = n_type


class NotEnoughNodesError(DeployError):
    def __init__(self, msg):
        self.msg = msg


class EnosG5kDuplicateJobsError(EnosError):
    def __init__(self, site, job_name):
        super(EnosG5kDuplicateJobsError, self).__init__(
            "Duplicate jobs on %s with the same name %s"
            % (site, job_name)
        )


class EnosG5kSynchronisationError(EnosError):
    def __init__(self, sites):
        super(EnosG5kSynchronisationError, self).__init__(
            "Unable to find a synchronised on %s" % sites)