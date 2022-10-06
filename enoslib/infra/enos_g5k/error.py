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
        super().__init__(f"Duplicate jobs on {site} with the same name {job_name}")


class EnosG5kSynchronisationError(EnosError):
    def __init__(self, sites):
        super().__init__(
            (
                "Unable synchronize the jobs on %s" % sites,
                "Try to make an explicit reservation instead",
            )
        )


class EnosG5kWalltimeFormatError(EnosError):
    def __init__(self):
        super().__init__("Walltime must be specified in HH:MM:SS format")


class EnosG5kReservationDateFormatError(EnosError):
    def __init__(self):
        super().__init__(
            "Reservation date must be specified in YYYY-MM-DD hh:mm:ss format"
        )
