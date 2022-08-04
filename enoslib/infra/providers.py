from datetime import datetime
from typing import List, Optional
from enoslib.errors import InvalidReservationError, NoSlotError
from enoslib.infra.provider import Provider
from enoslib.infra.utils import find_slot
from enoslib.objects import Networks, Roles


class Providers(Provider):
    def __init__(self, providers: List[Provider]):
        """A provider that syncs ressources of different infrastructures.

        Args:
            providers: List of Provider instances that you wish to use
        """
        self.providers = providers

    def init(
        self,
        time_window: Optional[int] = None,
        start_time: Optional[int] = None,
    ):
        """Tries to start the providers in providers list

        This calls the find_slot function in order to find a common free reservation
        date to all providers

        Args:
            time_window:
                How long in the future are you willing to look for for a start time
            start_time:
                The first start_time you will test, incremented after each try
                (5 minutes increment)

        Returns:
            Providers' roles and networks similar to
            :py:meth:`~enoslib.infra.provider.Provider.init` return value.

        Raises:
            NoSlotError: If no common slot can be found
        """
        if time_window is None:
            # TODO(msimonin): make it a global configuration
            time_window = 7200
        if start_time is None:
            # TODO(msimonin): make it a global configuration
            start_time = datetime.timestamp(datetime.now()) + 60

        while True:
            if start_time > time_window:
                raise NoSlotError()
            # Will raise a NoSlotError exception if no slot is found
            reservation_timestamp = find_slot(self.providers, time_window, start_time)
            roles = Roles()
            networks = Networks()
            providers_done = []
            for provider in self.providers:
                provider.set_reservation(reservation_timestamp)
                try:
                    provider_roles, provider_network = provider.init()
                    roles.extend(provider_roles)
                    roles[str(provider)] = provider_roles.all_roles()
                    networks.extend(provider_network)
                    networks[str(provider)] = provider_network.all_networks()
                    providers_done.append(provider)
                except InvalidReservationError as error:
                    for provider in providers_done:
                        provider.destroy()
                    _start_time = datetime.strptime(
                        error.time, "%Y-%m-%d %H:%M:%S"
                    ).timestamp()
                    time_window = time_window + (start_time - _start_time)
                    start_time = _start_time
                    break
            if len(providers_done) == len(self.providers):
                break
        return roles, networks

    def destroy(self):
        for provider in self.providers:
            provider.destroy()

    def test_slot(self, start_time: int):
        ok = True
        for provider in self.providers:
            ok = ok and provider.test_slot(start_time)
            if not ok:
                break
        return ok
