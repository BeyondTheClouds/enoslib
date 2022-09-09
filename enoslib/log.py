import logging
from typing import List, Optional


class TagsAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        prefix = ",".join(self.extra["tags"])
        return f"[{prefix}] {msg}", kwargs


def getLogger(name: str, tags: Optional[List[str]] = None) -> TagsAdapter:
    if tags is None:
        tags = None
    logger = TagsAdapter(logging.getLogger(__name__), dict(tags=tags))
    return logger
