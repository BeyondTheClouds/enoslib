from cmath import exp
from enoslib.infra.enos_iotlab import iotlab_api
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

        nodes_status = { "items": [
            {
                "state": "Alive",
                "network_address": "some_architecture.id.site",
                "archi": "test"
            } ]
        }
        experiments_status = { "items": [
            {
                "start_date": datetime.fromtimestamp(4).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 1,
                "nodes": [
                    "some_architecture.id.site"
                ],
            } ]
        }
        from datetime import datetime
        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 0, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 1, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 2, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 3, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 4, 4)
        self.assertFalse(ok)
        
        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 5, 4)
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

        nodes_status = { "items": [
            {
                "state": "Alive",
                "network_address": "some_architecture.id.site",
                "archi": "test"
            },
            {
                "state": "Alive",
                "network_address": "some_architecture.id2.site",
                "archi": "test"
            } ]
        }



        experiments_status = { "items": [
            {
                "start_date": datetime.fromtimestamp(4).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id.site"
                ],
            },
            {
                "start_date": datetime.fromtimestamp(0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id2.site"
                ],
            } ]
        }
        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 0, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 2, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 4, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 6, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, [], 8, 4)
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

        experiments_status = { "items": [
            {
                "start_date": datetime.fromtimestamp(4).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id.site",
                ],
            },
            {
                "start_date": datetime.fromtimestamp(0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id2.site"
                ],
            },
            {
                "start_date": datetime.fromtimestamp(4).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id2.site",
                ],
            }]
        }
        
        nodes_status = { "items": [
            {
                "state": "Alive",
                "network_address": "some_architecture.id.site",
                "archi": "test"
            },
            {
                "state": "Alive",
                "network_address": "some_architecture.id2.site",
                "archi": "test"
            } ]
        }

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 2, [], 0, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 2, [], 2, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 2, [], 4, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 2, [], 6, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 2, [], 8, 4)
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

        experiments_status = { "items": [
            {
                "start_date": datetime.fromtimestamp(4).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id.site"
                ],
            },
            {
                "start_date": datetime.fromtimestamp(0).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "submitted_duration": 4,
                "nodes": [
                    "some_architecture.id2.site"
                ],
            } ]
        }
        
        nodes_status = { "items": [
            {
                "state": "Alive",
                "network_address": "some_architecture.id.site",
                "archi": "test"
            },
            {
                "state": "Busy",
                "network_address": "some_architecture.id2.site",
                "archi": "test"
            } ]
        }

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, ["some_architecture.id2.site"], 0, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, ["some_architecture.id2.site"], 2, 4)
        self.assertFalse(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, ["some_architecture.id2.site"], 4, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, ["some_architecture.id2.site"], 6, 4)
        self.assertTrue(ok)

        ok = iotlab_api.nodes_availability(nodes_status, experiments_status, "test", 1, ["some_architecture.id2.site"], 8, 4)
        self.assertTrue(ok)
            