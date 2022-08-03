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


class TestUtils(EnosTest):
    @patch("enoslib.infra.providers.find_slot", return_value=0)
    def test_synchronized_reservation(
        self,
        mock_find_slot,
    ):
        host1 = Host("dummy-host1")
        host2 = Host("dummy-host2")
        network1 = DefaultNetwork("10.0.0.1/24")
        network2 = DefaultNetwork("10.0.0.2/24")

        class DummyProvider1(Provider):
            def __init__(self):
                pass

            def init(self):
                return (
                    Roles(Dummy=[host1]),
                    Networks(Dummy=[network1]),
                )

            def __str__(self):
                return "Dummy1"

        class DummyProvider2(Provider):
            def __init__(self):
                pass

            def init(self):
                return (
                    Roles(Dummy=[host2]),
                    Networks(Dummy=[network2]),
                )

            def __str__(self):
                return "Dummy2"

        provider1 = DummyProvider1()
        provider2 = DummyProvider2()
        providers = Providers([provider1, provider2])
        roles, networks = providers.init(0, start_time=0)
        assert str(provider1) in roles and str(provider2) in roles
        assert str(provider1) in networks and str(provider2) in networks
        assert host1 in roles["Dummy"] and host2 in roles["Dummy"]
        assert network1 in networks["Dummy"] and network2 in networks["Dummy"]

    def test_synchronized_reservation_busy_until(self):
        host = Host("dummy-host")
        network = DefaultNetwork("10.0.0.1/24")

        class DummyProvider(Provider):
            def __init__(self):
                pass

            def init(self):
                return (
                    Roles(Dummy=[host]),
                    Networks(Dummy=[network]),
                )

            def test_slot(self, start_time: int, time_window: int):
                pass

            def __str__(self):
                return "Dummy1"

        with patch.object(
            DummyProvider, "test_slot", side_effect=[False, True]
        ) as patch_find_slot:
            provider = DummyProvider()
            providers = Providers([provider])
            roles, networks = providers.init(1000, start_time=0)
            patch_find_slot.assert_called_with(300, 1000)

    def test_synchronized_reservation_init_raise_exception(self):
        host = Host("dummy-host")
        network = DefaultNetwork("10.0.0.1/24")

        class DummyProvider(Provider):
            def __init__(self):
                self.x = 0
                pass

            def init(self):
                if self.x == 0:
                    self.x += 1
                    raise (
                        InvalidReservationError(
                            datetime.fromtimestamp(500).strftime("%Y-%m-%d %H:%M:%S")
                        )
                    )
                return (
                    Roles(Dummy=[host]),
                    Networks(Dummy=[network]),
                )

            def test_slot(self, start_time: int, time_window: int):
                pass

            def __str__(self):
                return "Dummy1"

        with patch(
            "enoslib.infra.providers.find_slot", return_value=0
        ) as patch_find_slot:
            provider = DummyProvider()
            providers = Providers([provider])
            roles, networks = providers.init(1000, start_time=0, all_or_nothing=True)
            patch_find_slot.assert_called_with(
                providers.providers, 500, 500
            )  # 500, 500 because base start_time 0 and window 1000 so if start time = 500 then window = 500

    def test_synchronized_reservation_invalid(self):
        class DummyProvider(Provider):
            def __init__(self):
                pass

            def init():
                return ("Dummy", "Dummy")

            def test_slot(self, start_time: int, time_window: int):
                return False

        provider = DummyProvider()
        providers = Providers([provider])
        with self.assertRaises(NoSlotError):
            roles, networks = providers.init(1, 0)
