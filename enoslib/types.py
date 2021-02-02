# -*- coding: utf-8 -*-
from typing import Any, Dict, MutableMapping, List, Tuple

from .objects import Host

# FIXME remove this since we have an type for that now
Network = Dict[Any, Any]
Networks = List[Network]
Role = str
Roles = MutableMapping[Role, List[Host]]
RolesNetworks = Tuple[Roles, Networks]
