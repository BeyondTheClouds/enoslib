# -*- coding: utf-8 -*-
from typing import MutableMapping, List, Tuple

from .objects import Host, Network

# FIXME remove this since we have an type for that now
Networks = List[Network]
Role = str
Roles = MutableMapping[Role, List[Host]]
RolesNetworks = Tuple[Roles, Networks]
