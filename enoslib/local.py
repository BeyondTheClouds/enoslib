from .objects import Host


class LocalHost(Host):
    """Representation of your local machine."""

    def __init__(self, alias: str = "localhost"):
        super().__init__(
            address="localhost", alias=alias, extra={"ansible_connection": "local"}
        )
