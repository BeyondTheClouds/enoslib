from collections import namedtuple
from datetime import datetime
from typing import List
import yaml

from enoslib.errors import NoSlotError
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
from enoslib.infra.utils import find_slot
from enoslib.tests.unit import EnosTest

import ddt
from mock import patch

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
    clusters_status = {}
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
    experiments_status = {}
    experiments_status["items"] = []
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
                            "start_date": datetime.fromtimestamp(start_time).strftime(
                                "%Y-%m-%dT%H:%M:%SZ"
                            ),
                            "submitted_duration": walltime,
                            "nodes": [hostname],
                        }
                    )
                    # reset state
                    start_time = -1
                    walltime = 0

        if start_time != -1:
            # handle the case we're at the end of the line and thus we don't have any transition "*" -> "-"
            experiments_status["items"].append(
                {
                    "start_date": datetime.fromtimestamp(start_time).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": walltime,
                    "nodes": [hostname],
                }
            )
    return experiments_status


def parse_iot_status(status: str) -> dict:
    nodes_status = {}
    nodes_status["items"] = []
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
class TestUtils(EnosTest):
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
