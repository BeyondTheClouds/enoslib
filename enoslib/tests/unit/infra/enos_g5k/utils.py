from typing import List, Optional

from grid5000 import Grid5000Offline


class OfflineClient(Grid5000Offline):
    """Wrapper of the python-grid5000 offline client."""

    def __init__(self, data, excluded_sites: Optional[List] = None, **kwargs):
        """Constructor.

        Args:
            excluded_sites (list): sites to forget about when reloading the
                jobs. The primary use case was to exclude unreachable sites and
                allow the program to go on.
        """
        super().__init__(data, **kwargs)
        self.excluded_sites = excluded_sites if excluded_sites is not None else []


def get_offline_client():
    """Build on offline client.

    Allow to run (network isolated) tests against the reference API.
    """
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "reference.json").read_text())
    api = OfflineClient(data)
    # Allows the use of get_api_username()
    api.username = "dummy"
    return api
