# -*- coding: utf-8 -*-

from itertools import groupby
import logging
from typing import List, Optional
from enoslib.infra.enos_g5k.g5k_api_utils import _date2h
from enoslib.errors import InvalidReservationError

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

    Raises an InvalidReservationError exception if no slot is found
    """
    from datetime import datetime

    ko = True
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
        start_time = start_time + TIME_INCREMENT
    if ko:
        raise (InvalidReservationError("No valid time slot found"))
    logger.info("Reservation_date=%s" % (_date2h(start_time)))
    return start_time


def multi_sites_synchronized_reservation(
    providers: List[Provider],
    time_window: int,
    start_time: Optional[int] = None,
    all_or_nothing: bool = False,
):
    """Tries to start the providers in providers list

    This calls the find_slot function in order to find a common free reservation
    date to all providers

    Args:
        -providers: The list of all the providers the user wants to synchronize
        -time_window: How long in the future are you willing to look for for a start
        time
        -start_time: The first start_time you will test, incremented by 5 minutes
        each try
        -all_or_nothing: Set to true if you wish to cancel every reservations if one
        of them fail

    Returns:
        A dictionnary with provider's roles and a dictionnary with provider's networks
        indexed by the provider's name if found or None, None if a common date
        cannot be found

    """
    while True:
        reservation_timestamp = find_slot(providers, time_window, start_time)
        roles = {}
        networks = {}
        if reservation_timestamp is None:
            return None, None
        for provider in providers:
            providers_done = []
            provider.set_reservation(reservation_timestamp)
            try:
                roles[str(provider)], networks[str(provider)] = provider.init()
                providers_done.append(provider)
            except InvalidReservationError as error:
                if all_or_nothing:
                    for provider in providers_done:
                        provider.destroy()
                    search = re.findall(
                        r"""Reservation not valid --> KO \(This reservation could run at \d{4}-
                        \d{2}-\d{2} \d{2}:\d{2}:\d{2}\)""",
                        format(error),
                    )
                    start_time_string = re.findall(
                        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", search[0]
                    )[0]
                    _start_time = datetime.strptime(
                        start_time_string, "%Y-%m-%d %H:%M:%S"
                    ).timestamp()
                    time_window = time_window + (start_time - _start_time)
                    start_time = _start_time
                    break
                else:
                    continue
        if len(roles) == len(providers) or not all_or_nothing:
            break
    return roles, networks
