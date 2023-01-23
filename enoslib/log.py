import logging
from typing import MutableMapping, Optional, Sequence, Tuple


class TagsAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs) -> Tuple[str, MutableMapping]:
        prefix = ",".join(self.extra["tags"])  # type: ignore
        return f"[{prefix}] {msg}", kwargs


def getLogger(name: str, tags: Optional[Sequence[str]] = None) -> TagsAdapter:
    if tags is None:
        tags = None
    logger = TagsAdapter(logging.getLogger(__name__), dict(tags=tags))
    return logger


class DisableLogging:
    def __init__(self, level: Optional[int] = None):
        self.level = level

    def __enter__(self):
        if self.level is not None:
            logging.disable(self.level)

    def __exit__(self, et, ev, tb):
        logging.disable(logging.NOTSET)
        # implicit return of None => don't swallow exceptions
