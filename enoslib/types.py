# -*- coding: utf-8 -*-
from typing import Any, Dict, MutableMapping, List, Tuple

from .host import Host


Network = Dict[Any, Any]
Networks = List[Network]
Role = str
Roles = MutableMapping[Role, List[Host]]
RolesNetworks = Tuple[Roles, Networks]
