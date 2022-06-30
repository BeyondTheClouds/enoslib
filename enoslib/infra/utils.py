# -*- coding: utf-8 -*-

from itertools import groupby
import logging
from typing import List, Optional
from enoslib.infra.enos_g5k.g5k_api_utils import _date2h

from enoslib.infra.provider import Provider

logger = logging.getLogger(__name__)


def mk_pools(things, keyfnc=lambda x: x):
    "Indexes a thing by the keyfnc to construct pools of things."
    pools = {}
    sthings = sorted(things, key=keyfnc)
    for key, thingz in groupby(sthings, key=keyfnc):
        pools.setdefault(key, []).extend(list(thingz))
    return pools


def pick_things(pools, key, n):
    "Picks a maximum of n things in a dict of indexed pool of things."
    pool = pools.get(key)
    if not pool:
        return []
    things = pool[:n]
    del pool[:n]
    return things


def find_slot(
    providers: List[Provider], time_window: int, start_time: Optional[int] = None
) -> Optional[int]:
    """
    Search for a time slot at which all of the provider in "providers" are able to
    reserve their configurations
    time_window is how long in the future are we willing to be looking for
    start_time is when we start trying to look for a slot, by default a minute after
    the function is called
    """
    from datetime import datetime

    if start_time is None:
        start_time = datetime.timestamp(datetime.now()) + 60
    start_time_initial = start_time
    while start_time < start_time_initial + time_window:
        ko = False
        for provider in providers:
            ko = ko or not provider.test_slot(start_time, start_time + time_window)
            if ko:
                break
        if not ko:
            break
        start_time = start_time + 300
    if ko:
        return None
    logger.info("Reservation_date=%s" % (_date2h(start_time)))
    return start_time
