from datetime import datetime, timezone
from typing import Dict
from unittest.mock import patch, Mock, call
from collections import namedtuple

import ddt
import yaml
from freezegun import freeze_time

from enoslib.errors import InvalidReservationTime, InvalidReservationTooOld
from enoslib.errors import NegativeWalltime, NoSlotError
from enoslib.infra.enos_g5k.configuration import ClusterConfiguration
from enoslib.infra.enos_g5k.configuration import Configuration as G5k_Configuration
from enoslib.infra.enos_g5k.configuration import (
    NetworkConfiguration,
    ServersConfiguration,
)
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_iotlab.configuration import BoardConfiguration
from enoslib.infra.enos_iotlab.configuration import Configuration as IOTConfig
from enoslib.infra.enos_iotlab.configuration import PhysNodeConfiguration
from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.infra.providers import (
    find_slot,
    find_slot_and_start,
    start_provider_within_bounds,
)
from enoslib.infra.utils import offset_from_format, merge_dict
from enoslib.objects import DefaultNetwork, Host, Networks, Roles
from enoslib.tests.unit import EnosTest

# mimicking a grid5000.Status object (we only need to access the node attribute)
Status = namedtuple("Status", ["nodes"])


# time increment used in the graphical representation of the statuses
GANTT_INCREMENT = 300


def parse_g5k_request(g5k_request: str) -> G5k:
    config = G5k_Configuration()
    network = NetworkConfiguration(type="kavlan", site="rennes", roles=["role1"])
    for line in g5k_request.split("\n"):
        # walltime case
        if line.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            break
        line_args = line.rstrip("\n").split(" ")
        if len(line_args) == 1:
            config.add_machine_conf(
                ServersConfiguration(
                    servers=[line_args[0]],
                    roles=["test"],
                    primary_network=network,
                )
            )
        else:
            config.add_machine_conf(
                ClusterConfiguration(
                    cluster=line_args[0],
                    nodes=int(line_args[1]),
                    roles=["test"],
                    primary_network=network,
                )
            )
    config.walltime = line
    return G5k(config)


def parse_iot_request(iot_request: str) -> Iotlab:
    config = IOTConfig()
    for line in iot_request.split("\n"):
        if line.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            # walltime case
            break
        line_args = line.rstrip("\n").split(" ")
        if len(line_args) == 1:
            config.add_machine_conf(
                PhysNodeConfiguration(hostname=[line_args[0]], roles=["test"])
            )
        else:
            config.add_machine_conf(
                BoardConfiguration(
                    archi=line_args[0],
                    number=int(line_args[1]),
                    site=line_args[2],
                    roles=["test"],
                )
            )
    config.walltime = line
    return Iotlab(config)


def parse_g5k_clusters_status(status: str) -> dict:
    clusters_status: Dict = {}
    for line in status.split("\n"):
        if not line:
            continue
        args = line.rstrip("\n").split(" ")
        if len(args) == 1:
            current_cluster = args[0]
            clusters_status.setdefault(current_cluster, Status(nodes={}))
        else:
            gantt, hostname = args
            start_time = -1
            walltime = 0
            for i in range(0, len(gantt)):
                if gantt[i] == "*":
                    if start_time == -1:
                        start_time = i * GANTT_INCREMENT
                    walltime = walltime + GANTT_INCREMENT
                else:
                    if start_time != -1:
                        clusters_status[current_cluster].nodes.setdefault(
                            hostname, {"reservations": []}
                        )
                        clusters_status[current_cluster].nodes[hostname][
                            "reservations"
                        ].append(
                            {
                                "walltime": walltime,
                                "queue": "default",
                                "submitted_at": 0,
                                "scheduled_at": start_time,
                                "started_at": start_time,
                            }
                        )
                        start_time = -1
                        walltime = 0
            if start_time != -1:
                clusters_status[current_cluster].nodes.setdefault(
                    hostname, {"reservations": []}
                )
                clusters_status[current_cluster].nodes[hostname]["reservations"].append(
                    {
                        "walltime": walltime,
                        "queue": "default",
                        "submitted_at": 0,
                        "scheduled_at": start_time,
                        "started_at": start_time,
                    }
                )
    return clusters_status


def parse_iot_status_experiments(status: str) -> dict:
    experiments_status: Dict = {"items": []}
    for line in status.split("\n"):
        if not line:
            continue
        args = line.rstrip("\n").split(" ")
        gantt, hostname = args
        start_time = -1
        walltime = 0
        for i in range(0, len(gantt)):
            if gantt[i] == "*":
                if start_time == -1:
                    start_time = i * GANTT_INCREMENT
                walltime = walltime + GANTT_INCREMENT
            else:
                # transition "*" -> "-"
                if start_time != -1:
                    experiments_status["items"].append(
                        {
                            "start_date": datetime.fromtimestamp(
                                start_time, tz=timezone.utc
                            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "submitted_duration": int(walltime / 60),
                            "nodes": [hostname],
                        }
                    )
                    # reset state
                    start_time = -1
                    walltime = 0

        if start_time != -1:
            # handle the case we're at the end of the line and thus we don't
            # have any transition "*" -> "-"
            experiments_status["items"].append(
                {
                    "start_date": datetime.fromtimestamp(
                        start_time, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": int(walltime / 60),
                    "nodes": [hostname],
                }
            )
    return experiments_status


def parse_iot_status(status: str) -> dict:
    nodes_status: Dict = {"items": []}
    for line in status.split("\n"):
        if not line:
            break
        args = line.rstrip("\n").split(" ")
        hostname, archi, site = args
        nodes_status["items"].append(
            {
                "state": "Alive",
                "network_address": hostname,
                "archi": archi,
                "site": site,
            }
        )
    return nodes_status


def parse_statuses(fun):
    def wrapped(
        self,
        g5k_status,
        g5k_request,
        iot_status,
        iot_experiment_status,
        iot_request,
        expected,
    ):
        """At this stage the status file has been injected by ddt.

        So we parse them here and reinject them as the new parameters
        """
        with patch(
            "iotlabcli.auth.get_user_credentials", return_value=["test", "test"]
        ):
            with patch(
                "enoslib.infra.enos_g5k.configuration.get_cluster_site",
                return_value="siteA",
            ):
                g5k_provider = parse_g5k_request(g5k_request)
                iot_provider = parse_iot_request(iot_request)
                # dirty hack (changing the internal state) we should find a better way
                g5k_provider.clusters_status = parse_g5k_clusters_status(g5k_status)
                iot_provider.experiments_status = parse_iot_status_experiments(
                    iot_experiment_status
                )
                iot_provider.nodes_status = parse_iot_status(iot_status)

                return fun(self, g5k_provider, iot_provider, expected)

    return wrapped


@ddt.ddt
class TestFindSlot(EnosTest):
    @ddt.file_data("test_find_slot_meta.yaml", yaml.UnsafeLoader)
    @parse_statuses
    def test_ddt(self, g5k_provider, iot_provider, expected):
        if expected == "NoSlotError":
            with self.assertRaises(NoSlotError):
                find_slot([g5k_provider, iot_provider], 3600, start_time=0),
        else:
            self.assertEqual(
                find_slot([g5k_provider, iot_provider], 3600, start_time=0),
                eval(expected),
            )

    def test_find_slot_parameters(self):
        provider = Mock()
        with self.assertRaises(NoSlotError):
            find_slot([provider], -1, start_time=0)

        start_time = 42
        self.assertEqual(
            start_time,
            find_slot([], 10, start_time),
            "find_slot returns start time when the list of providers is empty",
        )

    @freeze_time("1970-01-01 00:00:00")
    def test_start_provider_within_bounds(self):
        provider = Mock()

        start_provider_within_bounds(provider, 80)
        # async_init is called with this new start_time
        provider.async_init.assert_called_with(start_time=80, time_window=0)

    @freeze_time("1970-01-01 00:00:00")
    def test_start_provider_within_bounds_start_time_too_close(self):
        host = Host("dummy-host1")
        network = DefaultNetwork("10.0.0.1/24")

        provider = Mock()
        provider.init.return_value = (Roles(Dummy=[host]), Networks(Dummy=[network]))

        start_provider_within_bounds(provider, 10)
        # now = 0 so we start at now + 60  = 60 to make sure to start in the
        # future
        # the walltime is reduced accordingly 10 - 60
        provider.offset_walltime.assert_called_with(-50)
        # async_init is called with this new start_time
        provider.async_init.assert_called_with(start_time=60, time_window=0)

    def test_start_provider_within_bounds_NegativeWalltime_error(self):
        provider = Mock()
        provider.offset_walltime.side_effect = [NegativeWalltime]

        with self.assertRaises(NoSlotError):
            start_provider_within_bounds(provider, 80)

    @freeze_time("1970-01-01 00:00:00")
    def test_start_provider_within_bounds_invalidReservationTime_error(self):
        provider = Mock()
        provider.async_init.side_effect = [
            InvalidReservationTime("1970-01-01 10:00:00")
        ]
        with self.assertRaises(InvalidReservationTime):
            start_provider_within_bounds(provider, 80)

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=60)
    def test_start_provider_within_bounds_three_retries(self):
        host = Host("dummy-host1")
        network = DefaultNetwork("10.0.0.1/24")

        provider = Mock()
        provider.async_init.side_effect = [
            InvalidReservationTooOld,
            InvalidReservationTooOld,
            (Roles(Dummy=[host]), Networks(Dummy=[network])),
        ]

        start_provider_within_bounds(provider, 60)
        provider.offset_walltime.assert_has_calls([call(0), call(-240), call(-360)])
        provider.async_init.assert_has_calls(
            [
                call(start_time=60, time_window=0),
                call(start_time=300, time_window=0),
                call(start_time=660, time_window=0),
            ]
        )

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=60)
    def test_start_provider_within_bounds_retry(self):

        provider = Mock()
        provider.async_init.side_effect = InvalidReservationTooOld

        with self.assertRaises(NoSlotError):
            start_provider_within_bounds(provider, 60)

    def test_do_init_provider_raise_NegativeWalltime(self):
        provider1 = Mock()
        provider1.offset_walltime.side_effect = NegativeWalltime
        with self.assertRaises(NoSlotError):
            start_provider_within_bounds(provider1, 0)

    def test_do_init_provider_raise_InvalidReservationTime(self):
        provider1 = Mock()
        provider1.offset_walltime.side_effect = InvalidReservationTime(
            "1970:01:01 01:00:00"
        )

        with self.assertRaises(InvalidReservationTime):
            start_provider_within_bounds(provider1, 0)

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=60)
    @patch("enoslib.infra.providers.find_slot", return_value=0)
    def test_find_slot_and_start(self, patch_find_slot):
        provider1 = Mock()
        provider1.is_created.return_value = False
        with patch(
            "enoslib.infra.providers.start_provider_within_bounds"
        ) as patch_do_init:
            find_slot_and_start([provider1], 0, 300)
            patch_do_init.assert_called_with(provider1, 0)

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=60)
    @patch(
        "enoslib.infra.providers.start_provider_within_bounds",
        return_side_effect=[0, 120],
    )
    def test_find_slot_and_start_init_failed(self, mock_find_slot):
        provider1 = Mock()
        provider1.is_created.return_value = False
        with patch(
            "enoslib.infra.providers.start_provider_within_bounds",
            side_effect=NoSlotError,
        ):
            with self.assertRaises(InvalidReservationTime):
                find_slot_and_start([provider1], 0, 500)

    @freeze_time("1970-01-01 00:00:00", auto_tick_seconds=60)
    def test_find_slot_and_start_no_slot_within_window(self):

        provider1 = Mock()
        provider1.test_slot.return_value = False
        provider1.is_created.return_value = False

        with self.assertRaises(NoSlotError):
            find_slot_and_start([provider1], 0, 300)


class TestOffsetFromFormat(EnosTest):
    def test_offset_from_format(self):
        actual = offset_from_format("00:00:00", 1, "%H:%M:%S")
        self.assertEqual("00:00:01", actual)

        actual = offset_from_format("00:00:00", 60, "%H:%M:%S")
        self.assertEqual("00:01:00", actual)

        actual = offset_from_format("00:00:00", 3600, "%H:%M:%S")
        self.assertEqual("01:00:00", actual)

        with self.assertRaises(NegativeWalltime):
            _ = offset_from_format("00:00:00", -1, "%H:%M:%S")

        exact = 2 * 3600 + 42 * 60 + 37
        actual = offset_from_format("02:42:37", -exact, "%H:%M:%S")
        self.assertEqual("00:00:00", actual)

        with self.assertRaises(NegativeWalltime):
            _ = offset_from_format("02:42:37", -(exact + 1), "%H:%M:%S")

        actual = offset_from_format("00:00", 1, "%H:%M")
        self.assertEqual("00:00", actual)

        actual = offset_from_format("00:00", 60, "%H:%M")
        self.assertEqual("00:01", actual)

        actual = offset_from_format("00:00", 3600, "%H:%M")
        self.assertEqual("01:00", actual)

        with self.assertRaises(NegativeWalltime):
            _ = offset_from_format("00:00", -1, "%H:%M")

        exact = 2 * 3600 + 42 * 60
        actual = offset_from_format("02:42", -exact, "%H:%M")
        self.assertEqual("00:00", actual)

        with self.assertRaises(NegativeWalltime):
            _ = offset_from_format("02:42", -(exact + 1), "%H:%M")


class TestMergeDict(EnosTest):
    def test_merge_all_in_one(self):
        original = {"a": 1}

        original = merge_dict(original, {"b": 2})
        self.assertDictEqual({"a": 1, "b": 2}, original)

        original = merge_dict(original, {"a": 42})
        self.assertDictEqual({"a": 42, "b": 2}, original)

        original = merge_dict(original, {"c": {"d": 1}})
        self.assertDictEqual({"a": 42, "b": 2, "c": {"d": 1}}, original)

        original = merge_dict(original, {"c": {"d": [1, 2, 3]}})
        self.assertDictEqual({"a": 42, "b": 2, "c": {"d": [1, 2, 3]}}, original)

        with self.assertRaises(ValueError):
            merge_dict(original, {"c": {"d": {}}})

        with self.assertRaises(ValueError):
            merge_dict(original, {"c": {"d": {}}})
