from typing import List

from .configuration import (
    ClusterConfiguration,
    GroupConfiguration,
    ServersConfiguration,
)
from .error import NotEnoughNodesError


class MinMixin:
    def raise_for_min(self):
        if self.config.min > len(self.oar_nodes):
            raise NotEnoughNodesError(
                f"Not enough servers: min {self.config.min}"
                f" requested but got {self.oar_nodes}"
            )


class ConcreteGroup(MinMixin):
    """Concretization of a cluster configuration (Base class)."""

    def __init__(self, oar_nodes: List[str], config: GroupConfiguration):
        self.oar_nodes = oar_nodes
        self.config = config


class ConcreteClusterConf(ConcreteGroup, MinMixin):
    """Concretization of a cluster configuration."""

    def __init__(self, oar_nodes: List[str], config: ClusterConfiguration):
        super().__init__(oar_nodes, config)


class ConcreteServersConf(ConcreteGroup, MinMixin):
    """Concretization of a servers' configuration."""

    def __init__(self, oar_nodes: List[str], config: ServersConfiguration):
        super().__init__(oar_nodes, config)
