from typing import Any, Dict, MutableMapping, List, Tuple

from .host import Host


class BaseConfigurationT:
    pass


NetworksT = List[Dict[Any, Any]]
RolesT = MutableMapping[str, List[Host]]
RolesNetworksT = Tuple[RolesT, NetworksT]