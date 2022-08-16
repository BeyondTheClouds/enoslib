import copy
from datetime import datetime
from math import ceil
from typing import List, Optional
from enoslib.errors import (
    InvalidReservationCritical,
    InvalidReservationTime,
    NoSlotError,
)
from enoslib.infra.provider import Provider
from enoslib.infra.utils import find_slot_and_start
from enoslib.objects import Roles, Networks


class Providers(Provider):
    def __init__(self, providers: List[Provider]):
        """A provider that syncs ressources of different infrastructures.

        Args:
            providers: List of Provider instances that you wish to use
        """
        self.providers = providers
        self.name = "-".join([str(p) for p in self.providers])

    def init(
        self,
        time_window: Optional[int] = None,
        start_time: Optional[int] = None,
        **kwargs
    ):
        """The provider to use when you want to sync multiple providers.

        This will call init on each provider after finding a common possible
        reservation date for each one of them. It uses
        :py:func:`~enoslib.infra.utils.find_slot` and
        :py:func:`~enoslib.infra.utils.start_provider_within_bounds` internally.


        Idempotency: ideally calling this function twice should reload existing
        reservations on each platform. However the current behaviour might
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
            roles[str(provider)] = _roles.all_hosts()
            networks.extend(_networks)
            networks[str(provider)] = _networks.all_networks()

        return roles, networks

    def _reserve(self, time_window: Optional[int], start_time: Optional[int], **kwargs):
        if time_window is None or time_window < 0:
            # TODO(msimonin): make it a global configuration
            time_window = 7200

        if start_time is None or start_time < 0:
            # TODO(msimonin): make it a global configuration
            start_time = ceil(datetime.timestamp(datetime.now()) + 60)

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
                _start_time = datetime.strptime(
                    error.time, "%Y-%m-%d %H:%M:%S"
                ).timestamp()
                time_window = time_window + (start_time - _start_time)
                start_time = _start_time
                continue
            except NoSlotError:
                self.destroy()
                raise InvalidReservationCritical(
                    "Unable to start the providers within given time window"
                )

    def async_init(
        self, time_window: Optional[int] = None, start_time: Optional[int] = None
    ):
        self._reserve(time_window=time_window, start_time=start_time)

    def destroy(self):
        for provider in self.providers:
            provider.destroy()

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
