from .objects import Host


class LocalHost(Host):
    """Representation of a local machine.

    Args:
        alias: alias for a local machine
            must be unique
    """

    def __init__(self, alias: str = "localhost"):
        super().__init__(
            address="localhost", alias=alias, extra={"ansible_connection": "local"}
        )
