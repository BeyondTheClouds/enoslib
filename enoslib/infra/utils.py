# -*- coding: utf-8 -*-

from itertools import groupby
import logging
from typing import List, Optional
from enoslib.infra.enos_g5k.g5k_api_utils import _date2h
from enoslib.errors import NoSlotError

from enoslib.infra.provider import Provider

logger = logging.getLogger(__name__)


TIME_INCREMENT = 300


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
) -> int:
    """
    Search for a time slot at which all of the provider in "providers" are able to
    reserve their configurations
    time_window is how long in the future are we willing to be looking for
    start_time is when we start trying to look for a slot, by default a minute after
    the function is called

    Raises:
        NoSlotError: If no compatible slot can be found for all provided providers
    """
    ko = True
    start_time_initial = start_time
    while start_time < start_time_initial + time_window:
        ko = False
        for provider in providers:
            ko = ko or not provider.test_slot(
                start_time, start_time_initial + time_window
            )
            if ko:
                break
        if not ko:
            break
        start_time = start_time + TIME_INCREMENT
    if ko:
        raise NoSlotError()
    logger.info("Reservation_date=%s" % (_date2h(start_time)))
    return start_time
