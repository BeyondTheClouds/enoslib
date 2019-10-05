# -*- coding: utf-8 -*-
import copy
from dataclasses import dataclass, field, InitVar
from typing import Dict, Optional


@dataclass
class Host(object):
    address: str
    alias: InitVar[str] = field(default=None, init=True)
    user: Optional[str] = None
    keyfile: Optional[str] = None
    port: Optional[int] = None
    extra: InitVar[Dict] = field(default=dict(), init=True)

    def __post_init__(self, alias, extra):
        self.alias = alias
        if alias is None:
            self.alias = self.address
        self.extra = extra or {}

    def to_dict(self):
        return copy.deepcopy(self.__dict__)

    @classmethod
    def from_dict(cls, d):
        _d = copy.deepcopy(d)
        address = _d.pop("address")
        return cls(address, **_d)

    def to_host(self):
        """Copy or coerce to a Host."""
        return Host(
            self.address,
            alias=self.alias,
            user=self.user,
            keyfile=self.keyfile,
            port=self.port,
            extra=self.extra,
        )

    def __str__(self):
        args = [
            self.alias,
            "address=%s" % self.address,
            "user=%s" % self.user,
            "keyfile=%s" % self.keyfile,
            "port=%s" % self.port,
            "extra=%s" % self.extra,
        ]
        return "Host(%s)" % ", ".join(args)
