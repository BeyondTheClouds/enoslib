import copy
from pathlib import Path
from typing import List, MutableSequence
from unittest.mock import patch

from ddt import data, ddt

from enoslib.infra.enos_g5k import g5k_api_utils
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    NetworkConfiguration,
    ServersConfiguration,
)
from enoslib.infra.enos_g5k.constants import (
    NATURE_PROD,
    PROD,
    PROD_VLAN_ID,
    SLASH_16,
    SLASH_22,
)
from enoslib.infra.enos_g5k.error import MissingNetworkError, NotEnoughNodesError
from enoslib.infra.enos_g5k.g5k_api_utils import OarNetwork
from enoslib.infra.enos_g5k.objects import G5kNetwork, G5kSubnetNetwork
from enoslib.infra.enos_g5k.provider import (
    _concretize_networks,
    _concretize_nodes,
    _join,
)
from enoslib.infra.enos_g5k.utils import get_ssh_keys
from enoslib.tests.unit import EnosTest


class TestConcretizeNetwork(EnosTest):
    def setUp(self):
        self.networks = [
            NetworkConfiguration(
                type="kavlan", site="rennes", id="roles1", roles=["role1"]
            ),
            NetworkConfiguration(
                type="kavlan", site="rennes", id="roles2", roles=["role2"]
            ),
        ]
        # used fot the subnet testing
        self.subnets = [
            NetworkConfiguration(
                type=SLASH_22, site="rennes", id="role1", roles=["role1"]
            ),
            NetworkConfiguration(
                type=SLASH_16, site="rennes", id="role2", roles=["role2"]
            ),
        ]

    def test_act(self):
        oar_networks = [
            OarNetwork(site="rennes", nature="kavlan", descriptor="4"),
            OarNetwork(site="rennes", nature="kavlan", descriptor="5"),
        ]
        concrete = _concretize_networks(self.networks, oar_networks)
        self.assertEqual(concrete[0].vlan_id, oar_networks[0].descriptor)
        self.assertEqual(concrete[1].vlan_id, oar_networks[1].descriptor)

    def test_act_subnets_enough(self):
        _networks = [
            {"site": "rennes", "descriptor": "10.156.%s.0/22" % i, "nature": "slash_22"}
            for i in range(65)
        ]
        oar_networks = [OarNetwork(**n) for n in _networks]
        concrete: MutableSequence[G5kNetwork] = _concretize_networks(
            self.subnets, oar_networks
        )
        concrete_network_0 = concrete[0]
        if isinstance(concrete_network_0, G5kSubnetNetwork):
            self.assertCountEqual(
                [n.descriptor for n in oar_networks[0:1]], concrete_network_0.subnets
            )
        concrete_network_1 = concrete[1]
        if isinstance(concrete_network_1, G5kSubnetNetwork):
            self.assertCountEqual(
                [n.descriptor for n in oar_networks[1:]], concrete_network_1.subnets
            )

    def test_act_subnets_not_enough(self):
        oar_networks = [
            OarNetwork(site="rennes", nature="slash_22", descriptor=f"10.156.{i}.0/22")
            for i in range(33)
        ]
        concrete = _concretize_networks(self.subnets, oar_networks)
        concrete_network_1 = concrete[1]
        if isinstance(concrete_network_1, G5kSubnetNetwork):
            self.assertEqual(32, len(concrete_network_1.subnets))

    def test_prod(self):
        self.networks[0].type = PROD
        # self.networks[0].nature = PROD  # self.networks[0] is NetworkConfiguration
        oar_networks = [
            OarNetwork(site="rennes", nature="kavlan", descriptor="5"),
            OarNetwork(site="rennes", nature=NATURE_PROD, descriptor=PROD_VLAN_ID),
        ]

        g5k_networks = _concretize_networks(self.networks, oar_networks)
        self.assertEqual(PROD_VLAN_ID, g5k_networks[0].vlan_id)
        self.assertEqual("5", g5k_networks[1].vlan_id)
        self.assertEqual(["role1"], g5k_networks[0].roles)
        self.assertEqual(["role2"], g5k_networks[1].roles)

    def test_one_missing(self):
        oar_networks = [OarNetwork(site="rennes", nature="kavlan", descriptor="4")]
        with self.assertRaises(MissingNetworkError):
            _concretize_networks(self.networks, oar_networks)

    def test_not_order_dependent(self):
        oar_networks_1 = [
            OarNetwork(site="rennes", nature="kavlan", descriptor="4"),
            OarNetwork(site="rennes", nature="kavlan", descriptor="5"),
        ]
        oar_networks_2 = [oar_networks_1[1], oar_networks_1[0]]

        networks_1 = copy.deepcopy(self.networks)
        networks_2 = copy.deepcopy(self.networks)
        g5k_networks_1 = _concretize_networks(networks_1, oar_networks_1)
        g5k_networks_2 = _concretize_networks(networks_2, oar_networks_2)

        # concrete are filled following the order of the config
        if (
            g5k_networks_1[0].vlan_id is not None
            and g5k_networks_2[0].vlan_id is not None
        ):
            self.assertCountEqual(g5k_networks_1[0].vlan_id, g5k_networks_2[0].vlan_id)
        if (
            g5k_networks_1[1].vlan_id is not None
            and g5k_networks_2[1].vlan_id is not None
        ):
            self.assertCountEqual(g5k_networks_1[1].vlan_id, g5k_networks_2[1].vlan_id)


class TestConcretizeNodes(EnosTest):
    def setUp(self):
        self.machines = [
            ClusterConfiguration(
                roles=["compute"], nodes=1, cluster="foocluster", site="rennes"
            ),
            ClusterConfiguration(
                roles=["compute"], nodes=1, cluster="barcluster", site="rennes"
            ),
        ]

    def test_exact(self):
        n1 = "foocluster-1.rennes.grid5000.fr"
        n2 = "barcluster-2.rennes.grid5000.fr"
        nodes = [n1, n2]
        concrete_servers = _concretize_nodes(self.machines, nodes)
        self.assertCountEqual(concrete_servers[0].oar_nodes, [n1])
        self.assertCountEqual(concrete_servers[1].oar_nodes, [n2])

    def test_one_missing(self):
        n1 = "foocluster-1.rennes.grid5000.fr"
        nodes = [n1]
        concrete_servers = _concretize_nodes(self.machines, nodes)
        self.assertCountEqual(concrete_servers[0].oar_nodes, [n1])
        self.assertCountEqual(concrete_servers[1].oar_nodes, [])

    def test_same_cluster(self):
        n1 = "foocluster-1.rennes.grid5000.fr"
        n2 = "foocluster-2.rennes.grid5000.fr"
        nodes = [n1, n2]
        self.machines[1].cluster = "foocluster"
        concrete_servers = _concretize_nodes(self.machines, nodes)
        self.assertCountEqual(concrete_servers[0].oar_nodes, [n1])
        self.assertCountEqual(concrete_servers[1].oar_nodes, [n2])

    def test_not_order_dependent(self):
        n1 = "foocluster-1.rennes.grid5000.fr"
        n2 = "foocluster-2.rennes.grid5000.fr"
        n3 = "foocluster-3.rennes.grid5000.fr"
        nodes = [n1, n2, n3]
        self.machines[0].nodes = 2

        machines_1 = copy.deepcopy(self.machines)
        concrete_1 = _concretize_nodes(machines_1, nodes)

        nodes = [n2, n3, n1]
        machines_2 = copy.deepcopy(self.machines)
        concrete_2 = _concretize_nodes(machines_2, nodes)

        self.assertCountEqual(concrete_1[0].oar_nodes, concrete_2[0].oar_nodes)
        self.assertCountEqual(concrete_1[1].oar_nodes, concrete_2[1].oar_nodes)


class TestConcretizeNodesWithServers(EnosTest):
    def test_exact(self):
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        machines = [
            ServersConfiguration(roles=["compute"], servers=nodes, site="rennes")
        ]

        concrete = _concretize_nodes(machines, nodes)
        self.assertCountEqual(concrete[0].oar_nodes, nodes)

    def test_two_types_exact(self):
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        machines = [
            ServersConfiguration(roles=["compute"], servers=nodes, site="rennes"),
            ClusterConfiguration(
                roles=["compute"], nodes=1, cluster="barcluster", site="rennes"
            ),
        ]

        oar_nodes = nodes + ["barcluster-1.rennes.grid5000.fr"]
        concrete = _concretize_nodes(machines, oar_nodes)
        self.assertCountEqual(concrete[0].oar_nodes, nodes)
        self.assertCountEqual(
            concrete[1].oar_nodes, ["barcluster-1.rennes.grid5000.fr"]
        )

    def test_dispatch_with_servers(self):
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        machines = [
            ServersConfiguration(
                roles=["compute"], nodes=1, servers=nodes, site="rennes"
            ),
            ServersConfiguration(
                roles=["compute"], nodes=1, servers=nodes, site="rennes"
            ),
        ]

        concrete = _concretize_nodes(machines, nodes)
        # only one should be given
        self.assertCountEqual(
            ["foocluster-1.rennes.grid5000.fr"], concrete[0].oar_nodes
        )
        self.assertCountEqual(
            ["foocluster-2.rennes.grid5000.fr"], concrete[1].oar_nodes
        )


class TestConcretizeNodesMin(EnosTest):
    def setUp(self):
        self.machines = [
            ClusterConfiguration(
                roles=["compute"], nodes=1, cluster="foocluster", site="rennes"
            ),
            ClusterConfiguration(
                roles=["compute"], nodes=1, cluster="foocluster", min=1, site="rennes"
            ),
        ]

    def test_exact(self):
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        concrete = _concretize_nodes(self.machines, nodes)
        # filled in a second step
        self.assertCountEqual(
            concrete[0].oar_nodes, ["foocluster-2.rennes.grid5000.fr"]
        )
        # Description with min are filled first
        self.assertCountEqual(
            concrete[1].oar_nodes, ["foocluster-1.rennes.grid5000.fr"]
        )

    def test_one_missing(self):
        nodes = ["foocluster-1.rennes.grid5000.fr"]
        concrete = _concretize_nodes(self.machines, nodes)
        self.assertCountEqual(concrete[0].oar_nodes, [])
        self.assertCountEqual(
            concrete[1].oar_nodes, ["foocluster-1.rennes.grid5000.fr"]
        )

    def test_all_missing(self):
        nodes: List = []
        with self.assertRaises(NotEnoughNodesError):
            _concretize_nodes(self.machines, nodes)


class TestJoin(EnosTest):
    def setUp(self) -> None:
        n1 = NetworkConfiguration(type="kavlan", site="rennes", id="roles1")
        n2 = NetworkConfiguration(type="kavlan", site="rennes", id="roles2")

        self.networks = [n1, n2]
        self.machines = [
            ClusterConfiguration(
                roles=["compute"],
                nodes=1,
                cluster="foocluster",
                site="rennes",
                primary_network=n1,
            ),
            ClusterConfiguration(
                roles=["compute"],
                nodes=1,
                cluster="foocluster",
                min=1,
                site="rennes",
                primary_network=n2,
                secondary_networks=[n1],
            ),
        ]

    def test_exact(self):
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        cmachines = _concretize_nodes(self.machines, nodes)
        oar_networks = [
            OarNetwork(site="rennes", nature="kavlan", descriptor="4"),
            OarNetwork(site="rennes", nature="kavlan", descriptor="5"),
        ]
        networks = _concretize_networks(self.networks, oar_networks)
        hosts = _join(cmachines, networks)
        self.assertEqual(2, len(hosts))
        self.assertEqual(networks[0], hosts[0].primary_network)
        self.assertEqual([], hosts[0].secondary_networks)

        self.assertEqual(networks[1], hosts[1].primary_network)
        self.assertEqual([networks[0]], hosts[1].secondary_networks)


@ddt
class TestBuildReservationCriteria(EnosTest):
    def test_only_machines_one_site_cluster(self):
        c = ClusterConfiguration(
            roles=["role1"], nodes=1, site="site1", cluster="foocluster"
        )

        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual({"site1": ["{cluster='foocluster'}/nodes=1"]}, criteria)

    def test_only_machines_one_site_cluster_disks(self):
        c = ClusterConfiguration(
            roles=["role1"],
            nodes=1,
            site="site1",
            cluster="foocluster",
            reservable_disks=True,
        )

        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual(
            {
                "site1": [
                    "{(type='default' or type='disk') AND "
                    "cluster='foocluster'}/nodes=1"
                ]
            },
            criteria,
        )

    def test_only_machines_one_site_one_servers(self):
        _ = {"machines": [{"role": "role1", "servers": ["foo-1.site1.grid5000.fr"]}]}
        c = ServersConfiguration(roles=["role1"], servers=["foo-1.site1.grid5000.fr"])

        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual(
            {"site1": ["{network_address in ('foo-1.site1.grid5000.fr')}/nodes=1"]},
            criteria,
        )

    def test_only_machines_one_site_two_servers(self):
        c = ServersConfiguration(
            roles=["role1"],
            servers=["foo-1.site1.grid5000.fr", "foo-2.site1.grid5000.fr"],
        )
        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual(
            {
                "site1": [
                    "{network_address in ('foo-1.site1.grid5000.fr', "
                    "'foo-2.site1.grid5000.fr')}/nodes=2"
                ]
            },
            criteria,
        )

    def test_only_machines_one_site_two_servers_disks(self):
        c = ServersConfiguration(
            roles=["role1"],
            servers=["foo-1.site1.grid5000.fr", "foo-2.site1.grid5000.fr"],
            reservable_disks=True,
        )
        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual(
            {
                "site1": [
                    "{(type='default' or type='disk') AND "
                    "network_address in ('foo-1.site1.grid5000.fr', "
                    "'foo-2.site1.grid5000.fr')}/nodes=2"
                ]
            },
            criteria,
        )

    def test_only_machines_two_sites(self):
        c1 = ClusterConfiguration(
            roles=["role1"], nodes=1, cluster="foocluster", site="site1"
        )
        c2 = ClusterConfiguration(
            roles=["role1"], nodes=1, cluster="barcluster", site="site2"
        )
        criteria = g5k_api_utils._build_reservation_criteria([c1, c2], [])
        self.assertDictEqual(
            {
                "site1": ["{cluster='foocluster'}/nodes=1"],
                "site2": ["{cluster='barcluster'}/nodes=1"],
            },
            criteria,
        )

    def test_only_no_machines(self):
        c = ClusterConfiguration(
            roles=["role1"], nodes=0, cluster="foocluster", site="site1"
        )
        criteria = g5k_api_utils._build_reservation_criteria([c], [])
        self.assertDictEqual({}, criteria)

    @data("kavlan", "kavlan-local", "kavlan-global")
    def test_network_kavlan(self, value):
        n = NetworkConfiguration(roles=["role1"], type=value, site="site1")
        criteria = g5k_api_utils._build_reservation_criteria([], [n])
        self.assertDictEqual({"site1": ["{type='%s'}/vlan=1" % value]}, criteria)

    @data("slash_16", "slash_22")
    def test_network_subnet(self, value):
        n = NetworkConfiguration(roles=["role1"], type=value, site="site1")
        criteria = g5k_api_utils._build_reservation_criteria([], [n])
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
                "reservations": [{"walltime": 1, "scheduled_at": 1, "started_at": 1}]
            }
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 0, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 1, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 1.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 2, 1)
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
                "reservations": [{"walltime": 1, "scheduled_at": 1, "started_at": 1}]
            },
            "node2": {
                "reservations": [{"walltime": 1, "scheduled_at": 0, "started_at": 0}]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 0, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 1, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 1.5, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 1, [], 2, 1)
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
                "reservations": [{"walltime": 1, "scheduled_at": 1, "started_at": 1}]
            },
            "node2": {
                "reservations": [{"walltime": 1, "scheduled_at": 0, "started_at": 0}]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 0, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 1, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 1.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 2, 1)
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
                "reservations": [
                    {
                        "queue": "besteffort",
                        "walltime": 1,
                        "scheduled_at": 1,
                        "started_at": 1,
                    }
                ]
            },
            "node2": {
                "reservations": [{"walltime": 1, "scheduled_at": 0, "started_at": 0}]
            },
        }

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 0, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 0.5, 1)
        self.assertFalse(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 1, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 1.5, 1)
        self.assertTrue(ok)

        ok = g5k_api_utils.can_start_on_cluster(nodes_status, 2, [], 2, 1)
        self.assertTrue(ok)


class TestUtils(EnosTest):

    @patch("pathlib.Path.exists", return_value=False)
    def test_get_ssh_keys_dir_not_exists(self, mock_path_exists):
        with self.assertRaises(FileNotFoundError) as context_manager:
            _ = get_ssh_keys()

        self.assertEqual(
            str(context_manager.exception),
            "No .ssh folder found, please create a SSH key.",
        )

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.glob", return_value=[])
    def test_get_ssh_keys_no_file_in_dir(self, mock_path_exists, mock_file_exists):
        with self.assertRaises(FileNotFoundError) as context_manager:
            _ = get_ssh_keys()

        self.assertEqual(
            str(context_manager.exception),
            "No public SSH key found, please create one.",
        )

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.glob", return_value=[Path("ssh_key.pub")])
    @patch("pathlib.Path.read_text", return_value="\n")
    def test_get_ssh_keys_carriage_return_as_content(
        self, mock_path_exists, mock_file_exists, mock_keys_content
    ):
        with self.assertRaises(ValueError) as context_manager:
            _ = get_ssh_keys()

        self.assertEqual(
            str(context_manager.exception),
            "Empty SSH key files, please fix it.",
        )

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.glob", return_value=[Path("ssh_key.pub")])
    @patch("pathlib.Path.read_text", return_value=" ")
    def test_get_ssh_keys_space_as_content(
        self, mock_path_exists, mock_file_exists, mock_keys_content
    ):
        with self.assertRaises(ValueError) as context_manager:
            _ = get_ssh_keys()

        self.assertEqual(
            str(context_manager.exception),
            "Empty SSH key files, please fix it.",
        )

    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.glob", return_value=[Path("ssh_key.pub")])
    @patch("pathlib.Path.read_text", return_value="")
    def test_get_ssh_keys_no_content(
        self, mock_path_exists, mock_file_exists, mock_keys_content
    ):
        with self.assertRaises(ValueError) as context_manager:
            _ = get_ssh_keys()

        self.assertEqual(
            str(context_manager.exception),
            "Empty SSH key files, please fix it.",
        )

    @patch("pathlib.Path.exists", return_value=True)
    @patch(
        "pathlib.Path.glob", return_value=[Path("ssh_key_1.pub"), Path("ssh_key_2.pub")]
    )
    @patch("pathlib.Path.read_text", return_value="Content\n")
    def test_get_ssh_keys_file_content_carriage_return(
        self, mock_path_exists, mock_file_exists, mock_keys_content
    ):
        keys_content = get_ssh_keys()
        self.assertEqual("Content\n\nContent\n", keys_content)

    @patch("pathlib.Path.exists", return_value=True)
    @patch(
        "pathlib.Path.glob", return_value=[Path("ssh_key_1.pub"), Path("ssh_key_2.pub")]
    )
    @patch("pathlib.Path.read_text", return_value="Content")
    def test_get_ssh_keys_file_content(
        self, mock_path_exists, mock_file_exists, mock_keys_content
    ):
        keys_content = get_ssh_keys()
        self.assertEqual("Content\nContent", keys_content)
