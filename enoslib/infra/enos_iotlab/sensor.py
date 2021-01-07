# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Optional


@dataclass(unsafe_hash=True)
class Sensor(object):
    """
    Abstraction for sensors

    A Sensor is an abstraction for elements that are simpler than Host
    (i.e. cannot receive ssh connection nor run shell commands)
    """

    address: str
    alias: Optional[str] = field(default=None)

    def __post_init__(self):
        if not self.alias:
            self.alias = self.address

    def __str__(self):
        args = [
            self.alias,
            "address=%s" % self.address,
        ]
        return "Sensor(%s)" % ", ".join(args)