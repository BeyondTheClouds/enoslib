# -*- coding: utf-8 -*-
import copy
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(unsafe_hash=True)
class Host(object):
    """Abstract unit of computation.

    A Host is anything EnosLib can SSH to and run shell commands on.
    It is an abstraction notion of unit of computation that can be
    bound to bare-metal machines, virtual machines, or containers.

    """

    address: str
    alias: Optional[str] = field(default=None)
    user: Optional[str] = None
    keyfile: Optional[str] = None
    port: Optional[int] = None
    # Two Hosts have the same hash if we can SSH on each of them in
    # the same manner (don't consider extra info in `__hash__()` that
    # are added, e.g., by enoslib.api.discover_networks).
    extra: Dict = field(default_factory=dict, hash=False)

    def __post_init__(self):
        if not self.alias:
            self.alias = self.address

        if self.extra:
            self.extra = copy.deepcopy(self.extra)

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
