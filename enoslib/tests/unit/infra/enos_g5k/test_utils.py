import copy

from ddt import ddt, data
import execo_g5k as ex5
from execo_g5k import api_utils as api
import mock

from enoslib.infra.enos_g5k import utils, g5k_api_utils
from enoslib.infra.enos_g5k.error import (MissingNetworkError,
                                          NotEnoughNodesError)
from enoslib.infra.enos_g5k.schema import KAVLAN, PROD, SLASH_22, SLASH_18
from enoslib.tests.unit import EnosTest


# TODO(msimonin): use patch
class TestMountNics(EnosTest):

    def setUp(self):
        self.c_resources = {
            "machines":[{
                "primary_network": "network_1",
                "cluster": "foo"
            }],
            "networks":[{
                "id": "network_1",
                "roles": ["n1", "n2"]
            }]
        }

    @mock.patch("enoslib.infra.enos_g5k.utils._mount_secondary_nics")
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_cluster_interfaces", return_value=[("eth0", "en0")])
    def test_primary(self, mock__mount_secondary_nics, mock_get_cluster_interfaces):
        utils.mount_nics(self.c_resources)
        self.assertCountEqual([("en0", ["n1", "n2"])], self.c_resources["machines"][0]["_c_nics"])


class TestMountSecondaryNics(EnosTest):

    def test_exact(self):
        desc = {
            "cluster": "foocluster",
            "_c_nodes": ["foocluster-1", "foocluster-2"],
            "secondary_networks": ["network_1", "network_2"]
        }
        networks = [
            {
                "type": KAVLAN,
                "id": "network_1",
                "role": "net_role_1",
                "site": "rennes",
                "_c_network": utils.ConcreteVlan(site="rennes", vlan_id="4")
            },
            {
                "type": KAVLAN,
                "id": "network_2",
                "roles": ["net_role_2", "net_role_3"],
                "site": "rennes",
                "_c_network": utils.ConcreteVlan(site="rennes", vlan_id="5")}
        ]
        g5k_api_utils.get_cluster_interfaces = mock.MagicMock(return_value=[("eth0", "en0"), ("eth1", "en1")])
        g5k_api_utils.set_nodes_vlan = mock.Mock()
        gk = mock.Mock()
        utils._mount_secondary_nics(desc, networks)
        self.assertCountEqual([("en0", ["net_role_1"]), ("en1", ["net_role_2", "net_role_3"])], desc["_c_nics"])


class TestConcretizeNetwork(EnosTest):

    def setUp(self):
        self.resources = {
            "networks":[{
                "type": KAVLAN,
                "site": "rennes",
                "id": "role1"
            }, {
                "type": KAVLAN,
                "site": "rennes",
                "id": "role2"
            }]
        }
        # used fot the subnet testing
        self.resources_subnet = {
            "networks": [{
                "type": SLASH_22,
                "site": "rennes",
                "id": "role1"
            }, {
                "type": SLASH_18,
                "site": "rennes",
                "id": "role1"
            }]
        }

    def test_act(self):
        _networks = [
            {"site": "rennes", "vlan_id": 4, "nature": "kavlan", "network": "1.2.3.4/24"},
            {"site": "rennes", "vlan_id": 5, "nature": "kavlan", "network": "2.2.3.4/24"}
        ]
        networks = [utils.ConcreteVlan(**n) for n in _networks]
        utils.concretize_networks(self.resources, networks)
        self.assertEqual(networks[0], self.resources["networks"][0]["_c_network"])
        self.assertEqual(networks[1], self.resources["networks"][1]["_c_network"])


    def test_act_subnets(self):
        _networks = [
            {"site": "rennes", "network": "10.156.1.0/18", "nature": "slash_18"},
            {"site": "rennes", "network": "10.156.0.0/22", "nature": "slash_22"},
        ]
        networks = [utils.ConcreteSubnet(**n) for n in _networks]
        utils.concretize_networks(self.resources_subnet, networks)
        self.assertEqual(networks[1], self.resources_subnet["networks"][0]["_c_network"])
        self.assertEqual(networks[0], self.resources_subnet["networks"][1]["_c_network"])


    def test_prod(self):
        self.resources["networks"][0]["type"] = PROD
        self.resources["networks"][0]["nature"] = PROD
        networks = [
            utils.ConcreteVlan(**{"site": "rennes", "vlan_id": 5, "nature": "kavlan","network": "1.2.3.4/24"}),
            utils.ConcreteProd(**{"site": "rennes", "nature": PROD, "network": "2.2.3.4/24"})
        ]

        utils.concretize_networks(self.resources, networks)
        # self.assertEqual(networks[0], self.resources["networks"][0]["_c_network"])
        self.assertEqual(None, self.resources["networks"][0]["_c_network"].vlan_id)
        self.assertEqual(networks[0], self.resources["networks"][1]["_c_network"])

    def test_one_missing(self):
        _networks = [
            {"site": "rennes", "vlan_id": 4, "nature": "kavlan", "network": "1.2.3.4/24"},
        ]

        networks = [utils.ConcreteVlan(**n) for n in _networks]
        with self.assertRaises(MissingNetworkError):
            utils.concretize_networks(self.resources, networks)

    def test_not_order_dependent(self):
        _networks_1 = [
            {"site": "rennes", "vlan_id": 4, "nature": "kavlan", "network": "1.2.3.4/24"},
            {"site": "rennes", "vlan_id": 5, "nature": "kavlan", "network": "2.2.3.4/24"}
        ]
        networks_1 = [utils.ConcreteVlan(**n) for n in _networks_1]
        networks_2 = [networks_1[1], networks_1[0]]

        resources_1 = copy.deepcopy(self.resources)
        resources_2 = copy.deepcopy(self.resources)
        utils.concretize_networks(resources_1, networks_1)
        utils.concretize_networks(resources_2, networks_2)

        self.maxDiff = None
        self.assertCountEqual(resources_1["networks"], resources_2["networks"])


class TestConcretizeNodes(EnosTest):

    def setUp(self):
        self.resources = {
            "machines": [{
                "role": "compute",
                "nodes": 1,
                "cluster": "foocluster",
            }, {
                "role": "compute",
                "nodes": 1,
                "cluster": "barcluster",
            }],
        }

    def test_exact(self):
        nodes = ["foocluster-1", "barcluster-2"]
        utils.concretize_nodes(self.resources, nodes)
        self.assertCountEqual(self.resources["machines"][0]["_c_nodes"],
                              ["foocluster-1"])
        self.assertCountEqual(self.resources["machines"][1]["_c_nodes"],
                              ["barcluster-2"])

    def test_one_missing(self):
        nodes = ["foocluster-1"]
        utils.concretize_nodes(self.resources, nodes)
        self.assertCountEqual(self.resources["machines"][0]["_c_nodes"],
                              ["foocluster-1"])
        self.assertCountEqual(self.resources["machines"][1]["_c_nodes"], [])


    def test_same_cluster(self):
        nodes = ["foocluster-1", "foocluster-2"]
        self.resources["machines"][1]["cluster"] = "foocluster"
        utils.concretize_nodes(self.resources, nodes)
        self.assertCountEqual(self.resources["machines"][0]["_c_nodes"],
                              ["foocluster-1"])
        self.assertCountEqual(self.resources["machines"][1]["_c_nodes"], ["foocluster-2"])

    def test_not_order_dependent(self):
        nodes = ["foocluster-1", "foocluster-2", "foocluster-3"]
        self.resources["machines"][0]["nodes"] = 2
        resources_1 = copy.deepcopy(self.resources)
        utils.concretize_nodes(resources_1, nodes)
        nodes = ["foocluster-2", "foocluster-3", "foocluster-1"]
        resources_2 = copy.deepcopy(self.resources)
        resources_2["machines"][0]["nodes"] = 2
        utils.concretize_nodes(resources_2, nodes)

        self.assertCountEqual(resources_1["machines"][0]["_c_nodes"],
                              resources_2["machines"][0]["_c_nodes"])



class TestConcretizeNodesMin(EnosTest):

    def setUp(self):
        self.resources = {
            "machines": [{
                "role": "compute",
                "nodes": 1,
                "cluster": "foocluster",
            }, {
                "role": "compute",
                "nodes": 1,
                "cluster": "foocluster",
                "min": 1
            }],
        }

    def test_exact(self):
        nodes = ["foocluster-1", "foocluster-2"]
        utils.concretize_nodes(self.resources, nodes)
        self.assertCountEqual(self.resources["machines"][0]["_c_nodes"],
                              ["foocluster-2"])
        # Description with min are filled first
        self.assertCountEqual(self.resources["machines"][1]["_c_nodes"],
                              ["foocluster-1"])

    def test_one_missing(self):
        nodes = ["foocluster-1"]
        utils.concretize_nodes(self.resources, nodes)
        self.assertCountEqual(self.resources["machines"][0]["_c_nodes"], [])
        self.assertCountEqual(self.resources["machines"][1]["_c_nodes"], ["foocluster-1"])

    def test_all_missing(self):
        nodes = []
        with self.assertRaises(NotEnoughNodesError):
            utils.concretize_nodes(self.resources, nodes)


@ddt
class TestBuildReservationCriteria(EnosTest):

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_cluster_site", return_value="site1")
    def test_only_machines_one_site(self, mock_get_cluster_site):
        resources = {
            "machines": [{
                "role": "role1",
                "nodes": 1,
                "cluster": "foocluster",
            }],
        }
        criteria = utils._build_reservation_criteria(resources["machines"], [])
        self.assertDictEqual({"site1": ["{cluster='foocluster'}/nodes=1"]}, criteria)


    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_cluster_site", side_effect=["site1", "site2"])
    def test_only_machines_two_sites(self, mock_get_cluster_site):
        resources = {
            "machines": [{
                "role": "role1",
                "nodes": 1,
                "cluster": "foocluster",
            }, {
                "role": "role2",
                "nodes": 2,
                "cluster": "barcluster"
            }],
        }
        criteria = utils._build_reservation_criteria(resources["machines"], [])
        self.assertDictEqual({
            "site1": ["{cluster='foocluster'}/nodes=1"],
            "site2": ["{cluster='barcluster'}/nodes=2"]
        }, criteria)

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_cluster_site", return_value="site1")
    def test_only_no_machines(self, mock_get_cluster_site):
        resources = {
            "machines": [{
                "role": "role1",
                "nodes": 0,
                "cluster": "foocluster",
            }],
        }
        criteria = utils._build_reservation_criteria(resources["machines"], [])
        self.assertDictEqual({}, criteria)


    @data("kavlan", "kavlan-local", "kavlan-global")
    def test_network_kavlan(self, value):
        resources = {
            "networks": [{
                "type": value,
                "site": "site1"
            }]
        }
        criteria = utils._build_reservation_criteria([], resources["networks"])
        self.assertDictEqual({"site1": ["{type='%s'}/vlan=1" % value]}, criteria)


    @data("slash_18", "slash_22")
    def test_network_subnet(self, value):
        resources = {
            "networks": [{
                "type": value,
                "site": "site1"
            }]
        }
        criteria = utils._build_reservation_criteria([], resources["networks"])
        self.assertDictEqual({"site1": ["%s=1" % value]}, criteria)

class TestGridStuffs(EnosTest):

    def test_can_start_on_cluster_1_1(self):
        """
        status:
            ----****----

        job:
            ****-------- 1, 0, 1
            --****------ 1, 0.5, 1
            ----****---- 1, 1, 1
            ------****-- 1, 1.5, 1
            --------**** 1, 2, 1
        """

        nodes_status = {
            "node1": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 1,
                    "started_at": 1
                }]
            }
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 0, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 1, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 1.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 2, 1)
        self.assertTrue(ok)


    def test_can_start_on_cluster_2_1(self):
        """
        status:
            ----****----
            ****--------

        job:
            ****-------- 1, 0, 1
            --****------ 1, 0.5, 1
            ----****---- 1, 1, 1
            ------****-- 1, 1.5, 1
            --------**** 1, 2, 1
        """

        nodes_status = {
            "node1": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 1,
                    "started_at": 1
                }]
            },
            "node2": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 0,
                    "started_at": 0
                }]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 0, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 1, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 1.5, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, 2, 1)
        self.assertTrue(ok)


    def test_can_start_on_cluster_2_2(self):
        """
        status:
            ----****----
            ****--------

        job:
            ****-------- 1, 0, 1
            --****------ 1, 0.5, 1
            ----****---- 1, 1, 1
            ------****-- 1, 1.5, 1
            --------**** 1, 2, 1
        """

        nodes_status = {
            "node1": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 1,
                    "started_at": 1
                }]
            },
            "node2": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 0,
                    "started_at": 0
                }]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 0, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 1, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 1.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 2, 1)
        self.assertTrue(ok)


    def test_can_start_on_cluster_2_2b(self):
        """
        status:
            ----bbbb----
            ****--------

        job:
            ****-------- 1, 0, 1
            --****------ 1, 0.5, 1
            ----****---- 1, 1, 1
            ------****-- 1, 1.5, 1
            --------**** 1, 2, 1
        """

        nodes_status = {
            "node1": {
                "reservations": [{
                    "queue": "besteffort",
                    "walltime": 1,
                    "scheduled_at": 1,
                    "started_at": 1
                }]
            },
            "node2": {
                "reservations": [{
                    "walltime": 1,
                    "scheduled_at": 0,
                    "started_at": 0
                }]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 0, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 1, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 1.5, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, 2, 1)
        self.assertTrue(ok)

