# -*- coding: utf-8 -*-
from typing import Any, Dict, MutableMapping, List, Tuple

from .host import Host

NetworkType = Union[IPv4Network, IPv6Network]
AddressType = Union[IPv4Address, IPv6Address]

# FIXME remove this since we have an type for that now
Network = Dict[Any, Any]
Networks = List[Network]
Role = str
Roles = MutableMapping[Role, List[Host]]
RolesNetworks = Tuple[Roles, Networks]
