class DeployError(Exception):
    pass


class MissingNetworkError(DeployError):
    def __init__(self, site, n_type):
        self.site = site
        self.n_type = n_type
