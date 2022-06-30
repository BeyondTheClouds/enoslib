from typing import List
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


def _build_iot_provider(machines: List[str], walltime: str) -> Iotlab:
    """
    Create a provider from a list of strings corresponded to the machines
    wanted and the walltime
    machines' items are under this format: "archi#number#site" or
    "hostname"
    """
    conf = IOTConfig()
    for machine in machines:
        if len(machine.split("#")) == 3:
            archi, number, site = machine.split("#")
            conf.add_machine_conf(
                BoardConfiguration(
                    archi=archi,
                    number=int(number),
                    site=site,
                    roles=["test"],
                )
            )
        else:
            if len(machine.split("#")) == 1:
                hostname = machine
                conf.add_machine_conf(
                    PhysNodeConfiguration(hostname=[hostname], roles=["test"])
                )
            else:
                continue
    conf.walltime = walltime
    conf.finalize()
    return Iotlab(conf)


def _build_g5k_provider(machines: List[str], walltime: str) -> G5k:
    """
    Create a provider from a list of strings corresponded to the machines wanted
    and the walltime
    machines' items are under this format:
    "cluster#nodes" or "hostname"
    """
    conf = G5k_Configuration()
    network = NetworkConfiguration(
        type="kavlan", site="rennes", id="roles1", roles=["role1"]
    )
    for machine in machines:
        len_machine = len(machine.split("#"))
        if len_machine == 1:
            server = machine
            conf.add_machine_conf(
                ServersConfiguration(
                    primary_network=network,
                    servers=[server],
                    roles=["test"],
                )
            )
        else:
            if len_machine == 2:
                cluster, nodes = machine.split("#")
                conf.add_machine_conf(
                    ClusterConfiguration(
                        primary_network=network,
                        cluster=cluster,
                        nodes=int(nodes),
                        roles=["test"],
                    )
                )
            else:
                continue
    conf.walltime = walltime
    conf.finalize()
    return G5k(conf)


IOT_NODES_STATUS = {
    "items": [
        {
            "state": "Alive",
            "network_address": "m3-1.lille.iot-lab.info",
            "archi": "m3:at86rf231",
            "site": "lille",
        },
        {
            "state": "Busy",
            "network_address": "m3-2.lille.iot-lab.info",
            "archi": "m3:at86rf231",
            "site": "lille",
        },
        {
            "state": "Alive",
            "network_address": "m3-3.lille.iot-lab.info",
            "archi": "m3:at86rf231",
            "site": "lille",
        },
    ]
}

IOT_EXPERIMENTS_STATUS = {
    "items": [
        {
            "start_date": datetime.fromtimestamp(30).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "submitted_duration": 60,
            "nodes": ["m3-1.lille.iot-lab.info"],
        },
        {
            "start_date": datetime.fromtimestamp(60).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "submitted_duration": 120,
            "nodes": ["m3-2.lille.iot-lab.info"],
        },
        {
            "start_date": datetime.fromtimestamp(60).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "submitted_duration": 60,
            "nodes": ["m3-3.lille.iot-lab.info"],
        },
    ]
}

G5K_NODES_STATUS = {
    "paravance": {
        "nodes": {
            "paravance-1.rennes.grid5000.fr": {
                "reservations": [
                    {
                        "walltime": 120,
                        "queue": "default",
                        "submitted_at": 60,
                        "scheduled_at": 60,
                        "started_at": 60,
                    }
                ]
            },
            "paravance-2.rennes.grid5000.fr": {
                "reservations": [
                    {
                        "walltime": 180,
                        "queue": "default",
                        "submitted_at": 120,
                        "scheduled_at": 120,
                        "started_at": 120,
                    }
                ]
            },
        }
    },
    "parasilo": {
        "nodes": {
            "parasilo-12.rennes.grid5000.fr": {
                "reservations": [
                    {
                        "walltime": 300,
                        "queue": "default",
                        "submitted_at": 60,
                        "scheduled_at": 60,
                        "started_at": 60,
                    }
                ]
            }
        }
    },
}


class TestUtils(EnosTest):
    @patch("iotlabcli.auth.get_user_credentials")
    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_synchronization_g5k_iot(self, mock_get_cluster_site, cred):

        """
        One - represents 30 seconds

        status iot:
        test-1.lille -**---------
        test-2.lille --****------
        test-3.lille --**--------

        job iot:
                     **********  2 machines, 10 units of time

        status g5k:
        paravance-1  --****------
        paravance-2  ----******--
        parasilo-12  --**********

        job g5k:
                     ********** 1 machine + parasilo-12, 10 units of time
        """

        cred.return_value = ["test", "test"]

        iot_provider = _build_iot_provider(["m3:at86rf231#2#lille"], "00:05")
        iot_provider.nodes_status = IOT_NODES_STATUS

        iot_provider.experiments_status = IOT_EXPERIMENTS_STATUS

        # This config should be free after 00:02:00

        g5k_provider = _build_g5k_provider(
            ["paravance#1", "parasilo-12.rennes.grid5000.fr"],
            "00:05:00",
        )
        g5k_provider.clusters_status = G5K_NODES_STATUS

        # This config should be free after 00:06:00

        assert (
            find_slot(
                providers=[g5k_provider, iot_provider], time_window=7200, start_time=0
            )
            == 600
        )

    @patch("iotlabcli.auth.get_user_credentials")
    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_synchronization_g5k_iot_fail_no_specific_machine_free_iot(
        self, mock_get_cluster_site, cred
    ):

        """
        One - represents 30 seconds

        status iot:
        test-1.lille -**---------
        test-2.lille --****------
        test-3.lille --**--------

        job iot:
                     **********  test-4.lille, 10 units of time

        status g5k:
        paravance-1  --****------
        paravance-2  ----******--
        parasilo-12  --**********

        job g5k:
                     ********** 1 machine + parasilo-12, 10 units of time
        """

        cred.return_value = ["test", "test"]
        iot_provider = _build_iot_provider(["test-4.lille.iot-lab.info"], "00:05")
        iot_provider.nodes_status = IOT_NODES_STATUS

        iot_provider.experiments_status = IOT_EXPERIMENTS_STATUS

        # This config should never be free

        g5k_provider = _build_g5k_provider(
            ["paravance#1", "parasilo-12.rennes.grid5000.fr"],
            "00:05:00",
        )
        g5k_provider.clusters_status = G5K_NODES_STATUS

        # This config should be free after 00:06:00

        assert (
            find_slot(
                providers=[g5k_provider, iot_provider], time_window=3600, start_time=0
            )
            is None
        )

    @patch("iotlabcli.auth.get_user_credentials")
    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_synchronization_g5k_iot_fail_no_specific_machine_free_g5k(
        self, mock_get_cluster_site, cred
    ):

        """
        One - represents 30 seconds

        status iot:
        test-1.lille -**---------
        test-2.lille --****------
        test-3.lille --**--------

        job iot:
                     **********  2 machines, 10 units of time

        status g5k:
        paravance-1  --****------
        paravance-2  ----******--
        parasilo-12  --**********

        job g5k:
                     ********** 1 machine + parasilo-13, 10 units of time
        """

        cred.return_value = ["test", "test"]
        iot_provider = _build_iot_provider(["m3:at86rf231#2#lille"], "00:05")
        iot_provider.nodes_status = IOT_NODES_STATUS

        iot_provider.experiments_status = IOT_EXPERIMENTS_STATUS

        # This config should be free after 00:02:00

        g5k_provider = _build_g5k_provider(
            ["paravance#1", "parasilo-13.rennes.grid5000.fr"],
            "00:05:00",
        )
        g5k_provider.clusters_status = G5K_NODES_STATUS

        # This config should never be free

        assert (
            find_slot(
                providers=[g5k_provider, iot_provider], time_window=3600, start_time=0
            )
            is None
        )
