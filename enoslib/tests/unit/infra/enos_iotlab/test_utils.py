from datetime import timezone
from typing import Dict

from enoslib.infra.enos_iotlab import iotlab_api
from enoslib.infra.enos_iotlab.configuration import (
    BoardConfiguration,
    Configuration,
    PhysNodeConfiguration,
)
from enoslib.tests.unit import EnosTest


class TestIotStuffs(EnosTest):
    def test_nodes_availability_1_1(self):
        """
        status:
            ----*----

        job:
            ****----- 1, 0, 4
            -****---- 1, 1, 4
            --****--- 1, 2, 4
            ---****-- 1, 3, 4
            ----****- 1, 4, 4
            -----**** 1, 5, 4
        """

        from datetime import datetime

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                }
            ]
        }
        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(
                        4 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 1,
                    "nodes": ["test-id.siteTest"],
                }
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(
            BoardConfiguration(archi="test:xxx", site="siteTest", number=1)
        )

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 1 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 3 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 5 * 60)
        self.assertTrue(ok)

    def test_nodes_availability_2_1(self):
        """
        status:
            ----****----
            ****--------

        job:
            ****-------- 1, 0, 4
            --****------ 1, 2, 4
            ----****---- 1, 4, 4
            ------****-- 1, 6, 4
            --------**** 1, 8, 4
        """

        from datetime import datetime

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
                {
                    "state": "Alive",
                    "network_address": "test-id2.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
            ]
        }

        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(
                        4 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": ["test-id.siteTest"],
                },
                {
                    "start_date": datetime.fromtimestamp(0, tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.siteTest"],
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(
            BoardConfiguration(archi="test:xxx", site="siteTest", number=1)
        )

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8 * 60)
        self.assertTrue(ok)

    def test_can_start_on_cluster_2_2(self):
        """
        status:
            ----****----
            ****oooo----

        job:
            ****-------- 2, 0, 4
            --****------ 2, 2, 4
            ----****---- 2, 4, 4
            ------****-- 2, 6, 4
            --------**** 2, 8, 4
        """

        from datetime import datetime

        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(
                        4 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": [
                        "test-id.siteTest",
                    ],
                },
                {
                    "start_date": datetime.fromtimestamp(
                        0 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.siteTest"],
                },
                {
                    "start_date": datetime.fromtimestamp(
                        4 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": [
                        "test-id2.siteTest",
                    ],
                },
            ]
        }

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
                {
                    "state": "Alive",
                    "network_address": "test-id2.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(
            BoardConfiguration(archi="test:xxx", site="siteTest", number=2)
        )

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8 * 60)
        self.assertTrue(ok)

    def test_can_start_on_cluster_3_1(self):
        """
        status:
            ----****----
            >id2--------

        job:
            >id2-------- 1, 0, 4
            -->id2------ 1, 2, 4
            ---->id2---- 1, 4, 4
            ------>id2-- 1, 6, 4
            -------->id2 1, 8, 4
        """

        from datetime import datetime

        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(
                        4 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": ["test-id.siteTest"],
                },
                {
                    "start_date": datetime.fromtimestamp(
                        0 * 60, tz=timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.siteTest"],
                },
            ]
        }

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
                {
                    "state": "Busy",
                    "network_address": "test-id2.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(PhysNodeConfiguration(hostname=["test-id2.siteTest"]))

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2 * 60)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6 * 60)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8 * 60)
        self.assertTrue(ok)

    def test_cannot_start_no_free_machine_on_site(self):
        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.siteTest",
                    "archi": "test:xxx",
                    "site": "siteTest",
                },
            ]
        }

        experiments_status: Dict = {"items": []}

        conf = Configuration().from_settings(walltime="00:01")
        conf.add_machine_conf(
            BoardConfiguration(archi="test:xxx", site="siteTest2", number=1)
        )
        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0)
        self.assertFalse(ok)
