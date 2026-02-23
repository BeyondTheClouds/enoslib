import logging
from itertools import groupby
from typing import Dict, Iterable, Mapping, TypeVar

from enoslib.errors import NegativeWalltime

logger = logging.getLogger(__name__)

_X = TypeVar("_X")


def mk_pools(things: Iterable, keyfnc=lambda x: x) -> Dict:
    """Indexes a thing by the keyfnc to construct pools of things."""
    pools: Dict = {}
    sthings = sorted(things, key=keyfnc)
    for key, thingz in groupby(sthings, key=keyfnc):
        pools.setdefault(key, []).extend(list(thingz))
    return pools


def pick_things(pools: Mapping, key, n: int):
    """Picks a maximum of n things in a dict of indexed pool of things."""
    pool = pools.get(key)
    if not pool:
        return []
    things = pool[:n]
    del pool[:n]
    return things


def offset_from_format(date_str: str, offset: int, fmt: str) -> str:
    import datetime as dt

    as_dt = dt.datetime.strptime(date_str, fmt)
    as_td = dt.timedelta(hours=as_dt.hour, minutes=as_dt.minute, seconds=as_dt.second)
    offset_as_td = dt.timedelta(seconds=offset)
    if as_td + offset_as_td < dt.timedelta(0):
        raise NegativeWalltime()
    new_as_dt = as_dt + offset_as_td
    return new_as_dt.strftime(fmt)


def _date2h(timestamp) -> str:
    # TODO(msimonin) use isoformat
    import time

    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    return t


def merge_dict(original: Dict, diff: Dict) -> Dict:
    """Merge original dict with a diff dict."""

    def _merge_dict(original: Dict, diff: Dict) -> Dict:
        """Merge inplace diff dict into original dict."""
        for k, v in diff.items():
            if k not in original:
                original[k] = v
                continue
            # The key exists on both side
            if isinstance(v, dict):
                if not isinstance(original[k], dict):
                    raise ValueError(
                        f"Mismatch type original={type(original[k])} vs diff=dict"
                    )
                # We  got a dict on both side, let's recurse
                _merge_dict(original[k], v)
            else:
                if isinstance(original[k], dict):
                    raise ValueError(f"Mismatch type original=dict vs diff={type(v)}")
                original[k] = v
        return original

    import copy

    result = copy.deepcopy(original)
    _merge_dict(result, diff)
    return result


def is_contained_in_order(iterable_1: Iterable[_X], iterable_2: Iterable[_X]) -> bool:
    """Verifies that every element from an iterable 1 appears in an iterable 2 in the
    same order.

    Args:
        iterable_1 (Iterable): The target iterable to find.
        iterable_2 (Iterable): The sequence to search within.

    Returns:
        bool: True if all elements from iterable 1 are found in the same order in
        iterable 2, else False
    """
    iterator_2 = iter(iterable_2)

    for element_1 in iterable_1:
        if element_1 not in iterator_2:
            return False

    return True
