# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from itertools import groupby
import logging
from math import ceil
from typing import List, Tuple
from enoslib.infra.enos_g5k.g5k_api_utils import _date2h
from enoslib.errors import InvalidReservationTime, InvalidReservationTooOld
from enoslib.errors import NegativeWalltime, NoSlotError

from enoslib.infra.provider import Provider
from enoslib.objects import Networks, Roles

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


def find_slot(providers: List[Provider], time_window: int, start_time: int) -> int:
    """
    Search for a time slot at which all of the provider in "providers" are able to
    reserve their configurations
    time_window is how long in the future are we willing to be looking for
    start_time is when we start trying to look for a slot, by default a minute after
    the function is called

    Args:
        providers:
            A list of providers
        time_window:
            How long in the future are you willing to look for for a start time
            Must be positive.
        start_time:
            The first start_time you will test, incremented after each try
            (5 minutes increment). Must be positive.

    Raises:
        NoSlotError: If no compatible slot can be found for all provided providers
    """
    ko = True
    start_time_initial = start_time
    # don't look for a slot if we exceed the time_window
    # but test one slot if time_window = 0
    while start_time <= start_time_initial + time_window:
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
    logger.info(
        "Common reservation_date=%s [%s providers]"
        % (_date2h(start_time), len(providers))
    )
    return start_time


def start_provider_within_bounds(provider: Provider, start_time: int, **kwargs):
    """Adjust provider walltime and reservation_date to fit into a slot

    Mutate the reservation/walltime attributes until finding a slot within
    [start_time, start_time + provider.walltime] where the provider can
    be started.

    The slot found is guaranteed to
    - not exceed the right bound (a negative walltime would raise an error)
      in the current implementation, we chose to work with a fixed end time.
    - and start in the future: start_time might be in the past, and reserving
      resources in the past is weird (and not allowed in some testbeds). We
      do our best to fiddle with the start_time to make sure it's in the
      future. If not we retry with an even further start_time.

    Finding the slot depends on a loop on error strategy which is stopped
    when the retry limit is hit or the walltime become to small. In both
    cases NoSlotError is raised.
    Otherwise the same errors as
    :py:meth:`~enoslib.infra.provider.Provider.init` can be raised (except
    InvalidReservationTooOld which can be catched internally)

    Raises:
        InvalidReservationTime: If a provider object cannot be initialized anymore,
        due to an update to it's related platform status since we first
        fetched it
        NoSlotError: If a Providers object cannot be initalized at its
        given start_time or if a provider fails to be initialized after too many
        retries.
    """
    for retry in range(3):
        try:
            now = ceil(datetime.now(timezone.utc).timestamp())
            # make sure the reservation is really in the future by adding an offset
            # (growing exponentially with the number of retries)
            candidate_start_time = int(max(now + 60 * (retry + 1) ** 2, start_time))
            # set the reservation date to this computed start_time
            provider.set_reservation(candidate_start_time)
            # also reduce accordingly the walltime to make sure we don't exceed to
            # initial right bound
            provider.offset_walltime(start_time - candidate_start_time)
            # let's move forward the start_time
            # - this allows for offsetting the walltime with the right value
            start_time = candidate_start_time
            # attempt to get the resources for this time slot
            provider.async_init(
                start_time=candidate_start_time, time_window=0, **kwargs
            )
            return
        except NegativeWalltime:
            # we did our best but the walltime is too short
            raise NoSlotError
        except InvalidReservationTooOld:
            # cover the case where the reservation date is still in the past
            # honestly with the offset we're adding this shouldn't really happen
            continue
        # all others exceptions are propagated to the user
    # we hit the retry limit
    raise NoSlotError


def find_slot_and_start(
    providers: List[Provider], start_time: int, time_window: int, **kwargs
) -> Tuple[Roles, Networks]:
    """Try to find a common time slot for all the Provider in providers to start and
    then start them

    This search for a reservation date that will fit all provider in providers and the
    call do_init with them on that found reservation date
    If this fail it will try to raise an error indicating a next possible
    slot if possible

    Raises:
        InvalidReservationTime: Happens if one of the provider cannot be initialized
        with reservation_timestamp as reservation date. Will provide an indication
        for a potential next possible time slot
    """
    # Don't look for a common date if a job is already running
    _providers = [p for p in providers if not p.is_created()]
    # Expected output here
    # - _providers is empty:
    #   ideal case we can proceed to find a common slot on for all of them
    # - _providers equals providers:
    #   normal case also, that means we're only reloading a previously init'ed
    #   Providers instance.
    # - providers have been partially init'ed
    #   This is an annoying corner case (e.g you ctrl-c in the middle of the
    #   Providers.init)
    if not _providers:
        return
    reservation_timestamp = find_slot(_providers, time_window, start_time)
    try:
        for provider in providers:
            start_provider_within_bounds(provider, start_time, **kwargs)
    except NoSlotError:
        # we transform to an InvalidReservationTime with a time hint
        # set to the next increment.
        slot_found = datetime.fromtimestamp(
        reservation_timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(
            f'Found slot {slot_found} turned out to be invalid'
        )
        raise InvalidReservationTime(
            datetime.fromtimestamp(start_time + TIME_INCREMENT,
                                   tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )


def offset_from_format(date_str: str, offset: int, fmt: str):
    import datetime as dt

    as_dt = dt.datetime.strptime(date_str, fmt)
    as_td = dt.timedelta(hours=as_dt.hour, minutes=as_dt.minute, seconds=as_dt.second)
    offset_as_td = dt.timedelta(seconds=offset)
    if as_td + offset_as_td < dt.timedelta(0):
        raise NegativeWalltime()
    new_as_dt = as_dt + offset_as_td
    return new_as_dt.strftime(fmt)
