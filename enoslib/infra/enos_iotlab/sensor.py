from dataclasses import dataclass, field
from typing import Dict

from enoslib.html import html_from_dict, repr_html_check
from enoslib.objects import BaseHost


@dataclass(unsafe_hash=True, order=True)
class Sensor(BaseHost):
    """
    Abstraction for sensors

    A Sensor is an abstraction for elements that are simpler than Host
    (i.e. cannot receive ssh connection nor run shell commands)
    """

    address: str
    alias: str = field(default="")

    def __post_init__(self):
        if self.alias == "":
            self.alias = self.address

    def __str__(self) -> str:
        return f"Sensor({self.alias}, address={self.address})"

    def to_dict(self) -> Dict:
        return {"alias": self.alias}

    @repr_html_check
    def _repr_html_(self, content_only=False) -> str:
        d = self.to_dict()
        name_class = f"{str(self.__class__)}@{hex(id(self))}"
        return html_from_dict(name_class, d, content_only=content_only)
