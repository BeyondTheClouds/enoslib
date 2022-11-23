from typing import List, MutableSequence

from .configuration import (
    ClusterConfiguration,
    GroupConfiguration,
    ServersConfiguration,
)
from .error import NotEnoughNodesError


class ConcreteGroup:
    def __init__(self, oar_nodes: MutableSequence[str], config: GroupConfiguration):
        self.oar_nodes: MutableSequence[str] = oar_nodes
        self.config: GroupConfiguration = config

    def raise_for_min(self):
        if self.config.min > len(self.oar_nodes):
            raise NotEnoughNodesError(
                f"Not enough servers: min {self.config.min}"
                f" requested but got {self.oar_nodes}"
            )


class ConcreteClusterConf(ConcreteGroup):
    """Realization of a cluster configuration."""

    def __init__(self, oar_nodes: List[str], config: ClusterConfiguration):
        super().__init__(oar_nodes, config)


class ConcreteServersConf(ConcreteGroup):
    """Realization of a servers' configuration."""

    def __init__(self, oar_nodes: List[str], config: ServersConfiguration):
        super().__init__(oar_nodes, config)
