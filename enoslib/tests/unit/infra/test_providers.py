from datetime import datetime
import unittest
from unittest.mock import MagicMock, Mock, patch
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.errors import InvalidReservationError, NoSlotError
from enoslib.infra.provider import Provider
from enoslib.infra.providers import Providers
from enoslib.objects import Host, Networks, Roles, DefaultNetwork
from enoslib.tests.unit import EnosTest


class TestFindSlot(EnosTest):
    """ Test high level synchronization logic between various providers.
    
    - test_synchronized_reservation: ideal case 
        a common slot is found, we check that the roles are merged correctly

    - test_synchronized_reservation_init_raise_exception:
        a common slot is found, but the reservation can't be made (e.g
        out-of-date planning at the time of the submission)
        we check that we jump to the hint wrapped in the exception

    - test_synchronized_reservation_possible_reservation_not_in_time_window:
        same as above but the hint is after the time window

    - test_start_time_exceed_time_window_raise_an_exception
    
    """
    @patch("enoslib.infra.providers.find_slot", return_value=0)
    def test_synchronized_reservation(
        self,
        mock_find_slot,
    ):
        host1 = Host("dummy-host1")
        host2 = Host("dummy-host2")
        network1 = DefaultNetwork("10.0.0.1/24")
        network2 = DefaultNetwork("10.0.0.2/24")

        provider1 = Mock()
        provider1.init.return_value = (Roles(Dummy=[host1]), Networks(Dummy=[network1]))

        provider2 = Mock()
        provider2.init.return_value = (Roles(Dummy=[host2]), Networks(Dummy=[network2]))

        providers = Providers([provider1, provider2])
        roles, networks = providers.init(time_window=0, start_time=0)
        assert str(provider1) in roles and str(provider2) in roles
        assert str(provider1) in networks and str(provider2) in networks
        assert host1 in roles["Dummy"] and host2 in roles["Dummy"]
        assert network1 in networks["Dummy"] and network2 in networks["Dummy"]


    def test_synchronized_reservation_init_raise_exception(self):
        host = Host("dummy-host")
        network = DefaultNetwork("10.0.0.1/24")
        roles, networks = Roles(Dummy=[host]), Networks(Dummy=[network]),
        
        with patch(
            "enoslib.infra.providers.find_slot", side_effect=[0, 500]
        ) as patch_find_slot:
            provider = Mock()
            provider.init.side_effect = [InvalidReservationError(datetime.fromtimestamp(500).strftime("%Y-%m-%d %H:%M:%S")), (roles, networks)]
            providers = Providers([provider])
            roles, networks = providers.init(time_window=1000, start_time=0)
            self.assertEqual(2, patch_find_slot.call_count, "find_slot must have been twice")
            # we assert on the last call of find_slot
            patch_find_slot.assert_called_with(
                [provider], 500, 500
            )  # 500, 500 because base start_time 0 and window 1000 so if start time = 500 then window = 500

    def test_synchronized_reservation_possible_reservation_not_in_time_window(self):
        provider = Mock()
        provider.init.side_effect = InvalidReservationError(datetime.fromtimestamp(1500).strftime("%Y-%m-%d %H:%M:%S"))
        providers = Providers([provider])
        with patch("enoslib.infra.providers.find_slot", return_value=500) as patch_find_slot:
            with self.assertRaises(NoSlotError):
               roles, networks = providers.init(1000, 0)


    def test_start_time_exceed_time_window_raise_an_exception(self):
        provider = Mock()
        providers = Providers([provider])
        with self.assertRaises(NoSlotError):
            providers.init(time_window=1000, start_time=1500)
