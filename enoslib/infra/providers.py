import copy
from datetime import datetime, timezone
from math import ceil
from typing import List, Optional
from enoslib.errors import (
    InvalidReservationCritical,
    InvalidReservationTime,
    InvalidReservationTooOld,
    NegativeWalltime,
    NoSlotError,
)

from enoslib.infra.provider import Provider
from enoslib.log import getLogger
from enoslib.objects import Roles, Networks

logger = getLogger(__name__, ["ProviderS"])

TIME_INCREMENT = 300


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
        "Common reservation_date=%s (local time) [%s providers]"
        % (datetime.fromtimestamp(start_time).isoformat(), len(providers))
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
    InvalidReservationTooOld which can be caught internally)

    Raises:
        InvalidReservationTime: If a provider object cannot be initialized anymore,
        due to an update to it's related platform status since we first
        fetched it
        NoSlotError: If a Providers object cannot be initialized at its
        given start_time or if a provider fails to be initialized after too many
        retries.
    """
    for retry in range(3):
        try:
            now = ceil(datetime.now(timezone.utc).timestamp())
            # make sure the reservation is really in the future by adding an offset
            # (growing exponentially with the number of retries)
            candidate_start_time = int(max(now + 60 * (retry + 1) ** 2, start_time))
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
            logger.info(f"Negative walltime occurred with {str(provider)}")
            # we did our best but the walltime is too short
            raise NoSlotError
        except InvalidReservationTooOld:
            logger.info(f"Invalid reservation too old occurred with {str(provider)}")

            # cover the case where the reservation date is still in the past
            # honestly with the offset we're adding this shouldn't really happen
            continue
        # all others exceptions are propagated to the user
    # we hit the retry limit
    raise NoSlotError


def find_slot_and_start(
    providers: List[Provider], start_time: int, time_window: int, **kwargs
) -> None:
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
    reservation = find_slot(_providers, time_window, start_time)
    try:
        logger.debug(
            "Attempt to start at %s"
            % (datetime.fromtimestamp(reservation).strftime("%Y-%m-%d %H:%M:%S"))
        )
        for provider in _providers:
            start_provider_within_bounds(provider, reservation, **kwargs)
        return
    except NoSlotError:
        # we transform to an InvalidReservationTime with a time hint
        # set to the next increment.
        slot_found = datetime.fromtimestamp(reservation, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        logger.debug(f"Found slot {slot_found} turned out to be invalid")
        raise InvalidReservationTime(
            datetime.fromtimestamp(start_time + TIME_INCREMENT, tz=timezone.utc)
        )


class Providers(Provider):
    def __init__(self, providers: List[Provider]):
        """A provider that syncs resources of different infrastructures.

        Args:
            providers: List of Provider instances that you wish to use
        """
        # super is finalizing the conf we can't send None here
        # super().__init__(None)
        self.providers = providers
        self.name = "-".join([str(p) for p in self.providers])

    def init(
        self,
        force_deploy: bool = False,
        start_time: Optional[int] = None,
        time_window: Optional[int] = None,
        **kwargs,
    ):
        """The provider to use when you want to sync multiple providers.

        This will call init on each provider after finding a common possible
        reservation date for each one of them. It uses
        :py:func:`~enoslib.infra.utils.find_slot` and
        :py:func:`~enoslib.infra.utils.start_provider_within_bounds` internally.


        Idempotency: ideally calling this function twice should reload existing
        reservations on each platform. However, the current behaviour might
        differ from this specification but we'll be happy to get your feedback
        on this.

        Args:
            time_window: duration in seconds
                How long in the future are you willing to look for a possible start time
            start_time: timestamp in seconds
                The first start_time you will test, incremented after each try
                (5 minutes increment)

        Returns:
            Providers' roles and networks similar to
            :py:meth:`~enoslib.infra.provider.Provider.init` return value.

        Raises:
            NoSlotError: If no common slot can be found
        """
        # Reserve the resources
        self._reserve(time_window=time_window, start_time=start_time, **kwargs)

        # actually reload the corresponding resources
        roles = Roles()
        networks = Networks()
        for provider in self.providers:
            # init will actually reload any existing reservation
            _roles, _networks = provider.init(**kwargs)
            roles.extend(_roles)
            roles[str(provider)] = _roles.all()
            networks.extend(_networks)
            networks[str(provider)] = _networks.all()
        return roles, networks

    def _reserve(self, time_window: Optional[int], start_time: Optional[int], **kwargs):
        if time_window is None or time_window < 0:
            # TODO(msimonin): make it a global configuration
            time_window = 7200
        if start_time is None or start_time < 0:
            # TODO(msimonin): make it a global configuration
            start_time = ceil(datetime.timestamp(datetime.now(timezone.utc)) + 60)
        while True:
            # Will raise a NoSlotError exception if no slot is found
            # reservation_timestamp >= start_time
            providers = copy.deepcopy(self.providers)
            try:
                # providers will be mutated in there
                find_slot_and_start(providers, start_time, time_window, **kwargs)
                # keep track of the providers states
                self.providers = providers
                return
            except InvalidReservationTime as error:
                self.destroy()
                # We hit a possible race condition
                # One of the provider did is best to start the job at start_time as
                # planned but failed.
                # That's because the status became out-of-date at the submission time.
                # So the strategy here is to try the find a new common slot given the
                # information of the error
                # (some providers are kind enough to provide a possible estimate
                # for start_time)
                _start_time = ceil(error.datetime.timestamp())
                logger.info(
                    "Local scheduler is proposing " f"{error.datetime.isoformat()}"
                )
                if _start_time <= start_time:
                    # The scheduler hint is weird
                    # some day we hit this behaviour where the scheduler hinted
                    # again and again the same date
                    # so we make sure to progress in this case
                    # by correcting the proposed date
                    _start_time = start_time + TIME_INCREMENT
                time_window = time_window + (start_time - _start_time)
                start_time = _start_time
                continue
            except NoSlotError:
                self.destroy()
                raise InvalidReservationCritical(
                    "Unable to start the providers within given time window"
                )

    def async_init(
        self,
        force_deploy: bool = False,
        start_time: Optional[int] = None,
        time_window: Optional[int] = None,
        **kwargs,
    ):
        self._reserve(time_window=time_window, start_time=start_time)

    def destroy(self):
        for provider in self.providers:
            provider.destroy(wait=True)

    def test_slot(self, start_time: int, end_time: int):
        ok = True
        for provider in self.providers:
            ok = ok and provider.test_slot(start_time, end_time)
            if not ok:
                break
        return ok

    def set_reservation(self, timestamp: int):
        for provider in self.providers:
            provider.set_reservation(timestamp)

    def offset_walltime(self, offset: int):
        for provider in self.providers:
            provider.offset_walltime(offset)

    def is_created(self) -> bool:
        for provider in self.providers:
            if not provider.is_created():
                return False
        return True
