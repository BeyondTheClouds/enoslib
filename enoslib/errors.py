# -*- coding: utf-8 -*-


class EnosError(Exception):
    pass


class EnosFailedHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosUnreachableHostsError(EnosError):
    def __init__(self, hosts):
        self.hosts = hosts


class EnosSSHNotReady(EnosError):
    def __init__(self, msg):
        super(EnosSSHNotReady, self).__init__(msg)


class EnosFilePathError(EnosError):
    def __init__(self, filepath, msg=''):
        super(EnosFilePathError, self).__init__(msg)
        self.filepath = filepath


# NOTE(msimonin): vital organs extraction doesn't use it currently
class EnosProviderMissingConfigurationKeys(EnosError):
    def __init__(self, missing_overridden):
        super(EnosProviderMissingConfigurationKeys, self).__init__(
            "Keys %s have to be overridden in the provider "
            "section of the reservation file."
            % missing_overridden)
        self.missing_ovorridden = missing_overridden
