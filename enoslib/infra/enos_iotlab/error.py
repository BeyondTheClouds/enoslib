# -*- coding: utf-8 -*-
from enoslib.errors import EnosError


class EnosIotlabCfgError(EnosError):
    def __init__(self, msg):
        self.msg = msg


class EnosIotlabWalltimeFormatError(EnosError):
    def __init__(self):
        super(EnosIotlabWalltimeFormatError, self).__init__(
            "Waltime must be specified in HH:MM:SS format"
        )
