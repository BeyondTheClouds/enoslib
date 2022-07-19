from typing import List
from enoslib.errors import InvalidReservationError
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    NetworkConfiguration,
    ServersConfiguration,
    Configuration as G5k_Configuration,
)
from enoslib.infra.enos_g5k.provider import G5k
from enoslib.infra.enos_iotlab.configuration import (
    BoardConfiguration,
    Configuration as IOTConfig,
    PhysNodeConfiguration,
)
from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.tests.unit import EnosTest
from enoslib.infra.utils import find_slot
from mock import patch
from datetime import datetime

from collections import namedtuple
# mimicking a grid5000.Status object (we only need to access the node attribute)
Status = namedtuple('Status', ['nodes'])

def parse_g5k_config(path: str) -> G5k:
    with open(f"enoslib/tests/unit/infra/Parsed_files_for_tests/{path}") as file:
        config = G5k_Configuration()
        network = NetworkConfiguration(
            type="kavlan", site="rennes", id="network1", roles=["role1"]
        )
        while True:
            line = file.readline()
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


def parse_iot_config(path: str) -> Iotlab:
    with open(f"enoslib/tests/unit/infra/Parsed_files_for_tests/{path}") as file:
        config = IOTConfig()
        while True:
            line = file.readline()
            if line.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
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


def parse_g5k_clusters_status(path: str) -> dict:
    clusters_status = {}
    with open(f"enoslib/tests/unit/infra/Parsed_files_for_tests/{path}") as file:
        while True:
            line = file.readline()
            if not line:
                break
            args = line.rstrip("\n").split(" ")
            if len(args) == 1:
                current_cluster = args[0]
                clusters_status.setdefault(current_cluster, Status(nodes={}))
            else:
                gantt = args[0]
                hostname = args[1]
                start_time = -1
                walltime = 0
                for i in range(0, len(gantt)):
                    if gantt[i] == "*":
                        if start_time == -1:
                            start_time = i * 30
                        walltime = walltime + 30
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


def parse_iot_status_experiments(path: str) -> dict:
    experiments_status = {}
    experiments_status["items"] = []
    with open(f"enoslib/tests/unit/infra/Parsed_files_for_tests/{path}") as file:
        while True:
            line = file.readline()
            if not line:
                break
            args = line.rstrip("\n").split(" ")
            gantt = args[0]
            hostname = args[1]
            start_time = -1
            walltime = 0
            for i in range(0, len(gantt)):
                if gantt[i] == "*":
                    if start_time == -1:
                        start_time = i * 30
                    walltime = walltime + 30
                else:
                    if start_time != -1:
                        experiments_status["items"].append(
                            {
                                "start_date": datetime.fromtimestamp(
                                    start_time
                                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "submitted_duration": walltime,
                                "nodes": [hostname],
                            }
                        )
                        start_time = -1
                        walltime = 0
            if start_time != 0:
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


def parse_iot_nodes_status(path: str) -> dict:
    nodes_status = {}
    nodes_status["items"] = []
    with open(f"enoslib/tests/unit/infra/Parsed_files_for_tests/{path}") as file:
        while True:
            line = file.readline()
            if not line:
                break
            args = line.rstrip("\n").split(" ")
            hostname = args[0]
            archi = args[1]
            site = args[2]
            nodes_status["items"].append(
                {
                    "state": "Alive",
                    "network_address": hostname,
                    "archi": archi,
                    "site": site,
                }
            )
    return nodes_status


class TestUtils(EnosTest):
    @patch("iotlabcli.auth.get_user_credentials")
    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_find_slot(self, mock_get_cluster_site, cred):
        cred.return_value = ["test", "test"]
        with open(
            "enoslib/tests/unit/infra/Parsed_files_for_tests/tests_to_make.txt"
        ) as file:
            while True:
                line = file.readline()
                if not line:
                    break
                args = line.rstrip("\n").split(" ")
                g5k_provider = parse_g5k_config(args[0])
                iot_provider = parse_iot_config(args[1])
                g5k_provider.clusters_status = parse_g5k_clusters_status(args[2])
                iot_provider.experiments_status = parse_iot_status_experiments(args[3])
                iot_provider.nodes_status = parse_iot_nodes_status(args[4])
                assert find_slot(
                    [g5k_provider, iot_provider], 3600, start_time=0
                ) == eval(args[5]), f"Line {line} failed"
