from cmath import exp
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
                    "network_address": "test-id.site",
                    "archi": "test:xxx",
                }
            ]
        }
        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(4).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 1,
                    "nodes": ["test-id.site"],
                }
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(BoardConfiguration(archi="test:xxx", number=1))

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 1)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 3)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 5)
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
                    "network_address": "test-id.site",
                    "archi": "test:xxx",
                },
                {
                    "state": "Alive",
                    "network_address": "test-id2.site",
                    "archi": "test:xxx",
                },
            ]
        }

        experiments_status = {
            "items": [
                {
                    "start_date": datetime.fromtimestamp(4).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id.site"],
                },
                {
                    "start_date": datetime.fromtimestamp(0).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.site"],
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(BoardConfiguration(archi="test:xxx", number=1))

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8)
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
                    "start_date": datetime.fromtimestamp(4).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": [
                        "test-id.site",
                    ],
                },
                {
                    "start_date": datetime.fromtimestamp(0).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.site"],
                },
                {
                    "start_date": datetime.fromtimestamp(4).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": [
                        "test-id2.site",
                    ],
                },
            ]
        }

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.site",
                    "archi": "test:xxx",
                },
                {
                    "state": "Alive",
                    "network_address": "test-id2.site",
                    "archi": "test:xxx",
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(BoardConfiguration(archi="test:xxx", number=2))

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8)
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
                    "start_date": datetime.fromtimestamp(4).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id.site"],
                },
                {
                    "start_date": datetime.fromtimestamp(0).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "submitted_duration": 4,
                    "nodes": ["test-id2.site"],
                },
            ]
        }

        nodes_status = {
            "items": [
                {
                    "state": "Alive",
                    "network_address": "test-id.site",
                    "archi": "test:xxx",
                },
                {
                    "state": "Busy",
                    "network_address": "test-id2.site",
                    "archi": "test:xxx",
                },
            ]
        }

        conf = Configuration.from_settings(walltime="00:04")
        conf.add_machine_conf(PhysNodeConfiguration(hostname=["test-id2.site"]))

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 0)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 2)
        self.assertFalse(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 4)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 6)
        self.assertTrue(ok)

        ok = iotlab_api.test_slot(conf, nodes_status, experiments_status, 8)
        self.assertTrue(ok)
