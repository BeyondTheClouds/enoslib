# -*- coding: utf-8 -*-


class DeployError(Exception):
    pass


class MissingNetworkError(DeployError):
    def __init__(self, site, n_type):
        self.site = site
        self.n_type = n_type


class NotEnoughNodesError(DeployError):
    def __init__(self, msg):
        self.msg = msg
