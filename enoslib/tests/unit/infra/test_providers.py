from datetime import datetime
from unittest.mock import Mock, patch, call

from enoslib.errors import (
    InvalidReservationCritical,
    InvalidReservationTime,
    NoSlotError,
)
from enoslib.infra.providers import Providers
from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.tests.unit import EnosTest
from freezegun import freeze_time
import pytz


class TestFindSlot(EnosTest):
    """Test high level synchronization logic between various providers.

    - test_synchronized_reservation: ideal case
        a common slot is found, we check that the roles are merged correctly

    - test_synchronized_reservation_init_raise_exception:
        a common slot is found, but the reservation can't be made (e.g.
        out-of-date planning at the time of the submission)
        we check that we jump to the hint wrapped in the exception

    - test_synchronized_reservation_possible_reservation_not_in_time_window:
        same as above but the hint is after the time window

    - test_start_time_exceed_time_window_raise_an_exception

    """

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=10)
    def test_synchronized_reservation(self):

        # now() is used now so that the time ticks forward by 10 seconds when
        # providers.init() will be called, simulating the time a request would
        # take
        datetime.now()

        host1 = Host("dummy-host1")
        host2 = Host("dummy-host2")
        network1 = DefaultNetwork("10.0.0.1/24")
        network2 = DefaultNetwork("10.0.0.2/24")

        provider1 = Mock()
        provider1.async_init.return_value = ...
        provider1.init.return_value = (Roles(Dummy=[host1]), Networks(Dummy=[network1]))
        provider1.__str__ = Mock()
        provider1.__str__.return_value = "provider1"

        provider2 = Mock()
        provider1.async_init.return_value = ...
        provider2.init.return_value = (Roles(Dummy=[host2]), Networks(Dummy=[network2]))
        provider2.__str__ = Mock()
        provider2.__str__.return_value = "provider2"

        providers = Providers([provider1, provider2])
        roles, networks = providers.init(time_window=500, start_time=0)
        self.assertTrue(str(provider1) in roles and str(provider2) in roles)
        self.assertTrue(str(provider1) in networks and str(provider2) in networks)
        self.assertTrue(host1 in roles["Dummy"] and host2 in roles["Dummy"])
        self.assertTrue(network1 in networks["Dummy"] and network2 in networks["Dummy"])

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=10)
    @patch(
        "enoslib.infra.providers.find_slot_and_start",
        side_effect=[
            InvalidReservationTime(
                pytz.timezone("UTC").localize(
                    datetime.fromisoformat("1970-01-01 00:01:00")
                )
            ),
            (Roles(), Networks()),
        ],
    )
    def test_synchronized_reservation_raise_InvalidReservationTime_in_UTC(
        self, patch_find_slot_and_start
    ):
        providers = Providers([])
        roles, networks = providers.init(time_window=300, start_time=0)
        patch_find_slot_and_start.assert_has_calls(
            [call([], 0, 300), call([], 60, 240)]
        )

    # in winter Europe/Paris is UTC+1
    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=10)
    @patch(
        "enoslib.infra.providers.find_slot_and_start",
        side_effect=[
            InvalidReservationTime(
                pytz.timezone("Europe/Paris").localize(
                    datetime.fromisoformat("1970-01-01 01:01:00")
                )
            ),
            (Roles(), Networks()),
        ],
    )
    def test_synchronized_reservation_raise_InvalidReservationTime_in_Paris(
        self, patch_find_slot_and_start
    ):
        providers = Providers([])
        roles, networks = providers.init(time_window=300, start_time=0)
        patch_find_slot_and_start.assert_has_calls(
            [call([], 0, 300), call([], 60, 240)]
        )

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=10)
    @patch("enoslib.infra.providers.find_slot_and_start", side_effect=NoSlotError)
    def test_synchronized_reservation_raise_InvalidReservationTime(
        self, patch_find_slot_and_start
    ):
        providers = Providers([])
        with self.assertRaises(InvalidReservationCritical):
            roles, networks = providers.init(time_window=300, start_time=0)

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=10)
    @patch(
        "enoslib.infra.providers.find_slot_and_start",
        side_effect=[
            InvalidReservationTime(
                pytz.timezone("UTC").localize(
                    datetime.fromisoformat("1970-01-01 00:01:00")
                )
            ),
            InvalidReservationTime(
                pytz.timezone("UTC").localize(
                    datetime.fromisoformat("1970-01-01 00:01:00")
                )
            ),
            (Roles(), Networks()),
        ],
    )
    def test_synchronized_reservation_raise_InvalidReservationTime_with_same_time(
        self, patch_find_slot_and_start
    ):
        providers = Providers([])
        roles, networks = providers.init(time_window=600, start_time=0)
        patch_find_slot_and_start.assert_has_calls(
            [call([], 0, 600), call([], 60, 540), call([], 360, 240)]
        )
