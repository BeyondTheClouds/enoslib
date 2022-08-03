from datetime import datetime
from typing import List, Optional
from enoslib.errors import InvalidReservationError
from enoslib.infra.provider import Provider
from enoslib.infra.utils import find_slot
from enoslib.objects import Networks, Roles


class Providers(Provider):
    """The provider to be used when deploying on multiple platforms

    Args:
        providers: List of Provider that you wish to deploy
    """

    def __init__(self, providers: List[Provider]):
        self.providers = providers

    def init(
        self,
        time_window: int,
        start_time: Optional[int] = None,
        all_or_nothing: bool = False,
    ):
        """Tries to start the providers in providers list

        This calls the find_slot function in order to find a common free reservation
        date to all providers

        Args:
            -time_window: How long in the future are you willing to look for for a start
            time
            -start_time: The first start_time you will test, incremented by 5 minutes
            each try
            -all_or_nothing: Set to true if you wish to cancel every reservations if one
            of them fail

        Returns:
            A dictionnary with provider's roles and a dictionnary with
            provider's networksindexed  by the provider's name if
            found or None, None if a common date cannot be found

        """
        while True:
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
                    if all_or_nothing:
                        for provider in providers_done:
                            provider.destroy()
                        _start_time = datetime.strptime(
                            error.time, "%Y-%m-%d %H:%M:%S"
                        ).timestamp()
                        time_window = time_window + (start_time - _start_time)
                        start_time = _start_time
                        break
                    else:
                        continue
            if len(providers_done) == len(self.providers) or not all_or_nothing:
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
