# -*- coding: utf-8 -*-
from enoslib.errors import EnosError


class EnosChameleonCfgError(EnosError):
    def __init__(self, msg):
        self.msg = msg


class EnosChameleonWalltimeFormatError(EnosError):
    def __init__(self):
        super(EnosChameleonWalltimeFormatError, self).__init__(
            "Walltime must be specified in HH:MM:SS format"
        )
