# -*- coding: utf-8 -*-
from enoslib.errors import EnosError


class EnosIotlabCfgError(EnosError):
    def __init__(self, msg):
        self.msg = msg


class EnosIotlabWalltimeFormatError(EnosError):
    def __init__(self):
        super(EnosIotlabWalltimeFormatError, self).__init__(
            "Walltime must be specified in HH:MM:SS format"
        )


class EnosIotlabStartTimeFormatError(EnosError):
    def __init__(self):
        super(EnosIotlabStartTimeFormatError, self).__init__(
            "Start time must be specified in YY-mm-dd HH:MM:SS format"
        )


class EnosIotLabPhysicalNodesError(EnosError):
    def __init__(self, msg):
        super(EnosIotLabPhysicalNodesError, self).__init__(msg)
