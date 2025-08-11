import ipaddress
from typing import List
from unittest import mock

from enoslib.api import STATUS_FAILED, STATUS_OK, CommandResult, Results
from enoslib.errors import NegativeWalltime
from enoslib.infra.enos_g5k.configuration import Configuration
from enoslib.infra.enos_g5k.error import (
    EnosG5kInvalidArgumentsError,
    EnosG5kKavlanNodesError,
)
from enoslib.infra.enos_g5k.g5k_api_utils import set_nodes_vlan
from enoslib.infra.enos_g5k.objects import (
    G5kEnosProd4Network,
    G5kEnosProd6Network,
    G5kEnosSubnetNetwork,
    G5kEnosVlan4Network,
    G5kEnosVlan6Network,
)
from enoslib.infra.enos_g5k.provider import (
    G5k,
    G5kHost,
    G5kProdNetwork,
    G5kSubnetNetwork,
    G5kVlanNetwork,
    _check_deployed_nodes,
    check_deployments,
)
from enoslib.tests.unit import EnosTest
from enoslib.tests.unit.infra.enos_g5k.utils import get_offline_client


class TestG5kEnos(EnosTest):
    def setUp(self) -> None:
        self.g5k_prod = G5kProdNetwork(roles=["role1"], id="a", site="rennes")
        self.g5k_kavlan = G5kVlanNetwork(
            roles=["role1"], id="a", site="rennes", vlan_id="4"
        )
        self.g5k_subnet = G5kSubnetNetwork(
            roles=["role1"], id="a", site="rennes", subnets=["10.0.0.0/24"]
        )

    def test_production(self):
        enos_prod = ipaddress.ip_network("172.16.0.0/16")
        enos_network: G5kEnosProd4Network = G5kEnosProd4Network(
            enos_prod, "172.16.0.254", "172.16.0.25"
        )
        self.assertFalse(enos_network.has_free_ips)
        self.assertCountEqual([], list(enos_network.free_ips))
        self.assertFalse(enos_network.has_free_macs)
        self.assertCountEqual([], list(enos_network.free_macs))

    def test_production6(self):
        enos_prod = ipaddress.ip_network("2001:660:4406:07::/64")
        enos_network: G5kEnosProd6Network = G5kEnosProd6Network(enos_prod, "::1", "::2")
        self.assertFalse(enos_network.has_free_ips)
        self.assertCountEqual([], list(enos_network.free_ips))
        self.assertFalse(enos_network.has_free_macs)
        self.assertCountEqual([], list(enos_network.free_macs))

    def test_kavlan(self):
        enos_kavlan_net_type = ipaddress.ip_network("10.24.0.0/18")
        enos_kavlan: G5kEnosVlan4Network = G5kEnosVlan4Network(
            enos_kavlan_net_type, "4", "172.16.0.254", "172.16.0.25"
        )
        self.assertTrue(enos_kavlan.has_free_ips)
        # There should be a lot of ips available in the worse case
        # (/20 network == local vlan) => some /24 contiguous subnet
        self.assertTrue(len(list(enos_kavlan.free_ips)) > 3000)
        # not clear about macs, so we kept them empty
        self.assertFalse(enos_kavlan.has_free_macs)

    def test_kavlan6(self):
        enos_kavlan_net_type = ipaddress.ip_network("2001:660:4406:0790::/64")
        enos_kavlan: G5kEnosVlan6Network = G5kEnosVlan6Network(
            enos_kavlan_net_type, "4", "1::", "2::"
        )
        self.assertTrue(enos_kavlan.has_free_ips)
        # There should be a lot of ips available in the worse case
        # (/20 network == local vlan) => some /24 contiguous subnet
        it_ips = enos_kavlan.free_ips
        # let's get some ips
        ips: List = []
        for i in range(3000):
            ips.append(next(it_ips))
        self.assertEqual(3000, len(ips))
        # not clear about macs, so we kept them empty
        self.assertFalse(enos_kavlan.has_free_macs)

    def test_subnet(self):
        enos_subnet_net_type = ipaddress.ip_network("10.140.0.0/22")
        enos_subnet: G5kEnosSubnetNetwork = G5kEnosSubnetNetwork(
            enos_subnet_net_type, "172.16.42.254", "172.16.42.25"
        )
        self.assertTrue(enos_subnet.has_free_ips)
        # we get rid of the first and last address of the /22
        # which leaves us with 1022 addresses
        self.assertEqual(1022, len(list(enos_subnet.free_ips)))
        self.assertTrue(enos_subnet.has_free_macs)
        self.assertEqual(1022, len(list(enos_subnet.free_macs)))

    def test_offset_walltime(self):
        conf = Configuration()
        conf.walltime = "02:00:00"
        provider = G5k(conf)
        provider.offset_walltime(-3600)
        self.assertEqual(provider.provider_conf.walltime, "01:00:00")

    def test_offset_walltime_negative_walltime(self):
        conf = Configuration()
        conf.walltime = "02:00:00"
        provider = G5k(conf)
        with self.assertRaises(NegativeWalltime):
            provider.offset_walltime(-7200)


class TestTranslate(EnosTest):
    def setUp(self):
        self.uids = ["paravance-1.rennes.grid5000.fr"]
        self.uid6s = ["paravance-1-ipv6.rennes.grid5000.fr"]
        self.uids_vlan = ["paravance-1-kavlan-6.rennes.grid5000.fr"]
        self.uid6s_vlan = ["paravance-1-kavlan-6-ipv6.rennes.grid5000.fr"]
        self.prod = G5kProdNetwork(roles=["role1"], id="1", site="rennes")
        self.kavlan = G5kVlanNetwork(
            roles=["role1"], id="1", site="rennes", vlan_id="6"
        )
        self.subnet = G5kSubnetNetwork(
            roles=["roles1"], id="1", site="rennes", subnets=["10.0.0.1/24"]
        )

    def test_production(self):
        # direct
        [(f, t)] = self.prod.translate(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uids[0], t)
        # reverse
        [(rf, rt)] = self.prod.translate([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)

    def test_production6(self):
        # direct
        [(f, t)] = self.prod.translate6(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uid6s[0], t)
        # reverse
        [(rf, rt)] = self.prod.translate6([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)

    def test_kavlan(self):
        # direct
        [(f, t)] = self.kavlan.translate(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uids_vlan[0], t)
        # reverse
        [(rf, rt)] = self.kavlan.translate([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)

    def test_kavlan6(self):
        # direct
        [(f, t)] = self.kavlan.translate6(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uid6s_vlan[0], t)
        # reverse
        [(rf, rt)] = self.kavlan.translate6([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)

    def test_subnet(self):
        # direct
        [(f, t)] = self.subnet.translate(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uids[0], t)
        # reverse
        [(rf, rt)] = self.subnet.translate([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)

    def test_subnet6(self):
        # direct
        [(f, t)] = self.subnet.translate6(self.uids)
        self.assertEqual(self.uids[0], f)
        self.assertEqual(self.uids[0], t)
        # reverse
        [(rf, rt)] = self.subnet.translate6([t], reverse=True)
        self.assertEqual(t, rf)
        self.assertEqual(self.uids[0], rt)


class TestKavlan(EnosTest):
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_set_nodes_vlan_multisite_error(self, mock_api):
        nodes = ["paravance-1.rennes.grid5000.fr", "grisou-1.nancy.grid5000.fr"]
        with self.assertRaises(EnosG5kInvalidArgumentsError):
            set_nodes_vlan(nodes, "eth1", "42")

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_set_nodes_vlan_kavlan_ok(self, mock_api):
        # Input data
        site = "rennes"
        nodes = ["paravance-1.rennes.grid5000.fr", "paravance-2.rennes.grid5000.fr"]
        interface = "eth1"
        vlan_id = "42"
        # Mock Kavlan API
        kavlan_api = mock.MagicMock()
        kavlan_api.sites[site].vlans[vlan_id].nodes.submit.return_value = {
            nodes[0]: {"status": "success", "message": "dummy"},
            nodes[1]: {"status": "success", "message": "dummy"},
        }
        mock_api.return_value = kavlan_api
        # Call mocked API
        set_nodes_vlan(nodes, interface, vlan_id)
        # Check calls
        kavlan_api.sites[site].vlans[vlan_id].nodes.submit.assert_called_once_with(
            [
                "paravance-1-eth1.rennes.grid5000.fr",
                "paravance-2-eth1.rennes.grid5000.fr",
            ]
        )

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_set_nodes_vlan_kavlan_unchanged(self, mock_api):
        # Input data
        site = "rennes"
        nodes = ["paravance-1.rennes.grid5000.fr", "paravance-2.rennes.grid5000.fr"]
        interface = "eth1"
        vlan_id = "42"
        # Mock Kavlan API
        kavlan_api = mock.MagicMock()
        kavlan_api.sites[site].vlans[vlan_id].nodes.submit.return_value = {
            nodes[0]: {"status": "success", "message": "dummy"},
            nodes[1]: {"status": "unchanged", "message": "dummy"},
        }
        mock_api.return_value = kavlan_api
        # Call mocked API
        set_nodes_vlan(nodes, interface, vlan_id)
        # Check calls
        kavlan_api.sites[site].vlans[vlan_id].nodes.submit.assert_called_once_with(
            [
                "paravance-1-eth1.rennes.grid5000.fr",
                "paravance-2-eth1.rennes.grid5000.fr",
            ]
        )

    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_set_nodes_vlan_kavlan_error(self, mock_api):
        # Input data
        site = "rennes"
        nodes = ["paravance-1.rennes.grid5000.fr", "paravance-2.rennes.grid5000.fr"]
        interface = "eth1"
        vlan_id = "42"
        # Mock Kavlan API
        kavlan_api = mock.MagicMock()
        kavlan_api.sites[site].vlans[vlan_id].nodes.submit.return_value = {
            nodes[0]: {"status": "success", "message": "dummy"},
            nodes[1]: {"status": "failure", "message": "error"},
        }
        mock_api.return_value = kavlan_api
        with self.assertRaises(EnosG5kKavlanNodesError):
            set_nodes_vlan(nodes, interface, vlan_id)


class TestCheckDeployedNode(EnosTest):
    @mock.patch("enoslib.infra.enos_g5k.provider.run")
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_check_deployed_nodes(self, mock_api, mock_run):
        mock_run.return_value = Results(
            [
                CommandResult(
                    host="plip-1.rennes.grid5000.fr",
                    task="Check deployment",
                    status=STATUS_OK,
                    payload={},
                ),
                CommandResult(
                    host="plip-2.rennes.grid5000.fr",
                    task="Check deployment",
                    status=STATUS_FAILED,
                    payload={},
                ),
            ]
        )
        mock_api.return_value = get_offline_client()
        net = G5kProdNetwork(["tag1"], "id", "rennes")
        node1 = G5kHost("plip-1.rennes.grid5000.fr", [], net)
        node2 = G5kHost("plip-2.rennes.grid5000.fr", [], net)
        deployed, undeployed = _check_deployed_nodes(net, [node1, node2])
        self.assertCountEqual([node1], deployed)
        self.assertCountEqual([node2], undeployed)


class TestCheckDeployments(EnosTest):
    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    def test_check_deployments_force(self, mock__check_deployed_nodes):
        net = G5kProdNetwork(["tag1"], "id", "rennes")
        node1 = G5kHost("plip-1.rennes.grid5000.fr", [], net)
        node2 = G5kHost("plip-2.rennes.grid5000.fr", [], net)

        # one undeployed
        mock__check_deployed_nodes.return_value = ([node1], [node2])
        already_deployed, configs = check_deployments([node1, node2], True, {})
        # force so no check
        self.assertEqual(0, mock__check_deployed_nodes.call_count)
        self.assertCountEqual([], already_deployed)
        self.assertEqual(1, len(configs))
        self.assertCountEqual([node1.fqdn, node2.fqdn], configs[0]["nodes"])

    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    def test_check_deployments_with_one_undeployed(self, mock__check_deployed_nodes):
        net = G5kProdNetwork(["tag1"], "id", "rennes")
        node1 = G5kHost("plip-1.rennes.grid5000.fr", [], net)
        node2 = G5kHost("plip-2.rennes.grid5000.fr", [], net)

        # one undeployed
        mock__check_deployed_nodes.return_value = ([node1], [node2])
        already_deployed, configs = check_deployments([node1, node2], False, {})
        self.assertEqual(1, mock__check_deployed_nodes.call_count)
        self.assertCountEqual([node1], already_deployed)
        self.assertEqual(1, len(configs))
        self.assertCountEqual([node2.fqdn], configs[0]["nodes"])

    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    def test_check_deployments_with_kavlan(self, mock__check_deployed_nodes):
        kavlan = G5kVlanNetwork(["net"], "id", "rennes", "4")
        node1 = G5kHost("plip-1.rennes.grid5000.fr", [], kavlan)

        # one undeployed
        mock__check_deployed_nodes.return_value = ([], [node1])
        already_deployed, configs = check_deployments([node1], False, {})
        self.assertEqual(1, mock__check_deployed_nodes.call_count)
        self.assertCountEqual([], already_deployed)
        self.assertEqual(1, len(configs))
        self.assertCountEqual([node1.fqdn], configs[0]["nodes"])
        # vlan_id is set under the vlan key
        self.assertCountEqual("4", configs[0]["vlan"])

    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    def test_check_deployments_multi_deployment(self, mock__check_deployed_nodes):
        net1 = G5kProdNetwork(["tag1"], "id1", "siteA")
        net2 = G5kProdNetwork(["tag1"], "id2", "siteB")
        node1 = G5kHost("plip-1.siteA.grid5000.fr", [], net1)
        node2 = G5kHost("plip-2.siteB.grid5000.fr", [], net2)

        # one undeployed for each site
        mock__check_deployed_nodes.side_effect = [([], [node1]), ([], [node2])]

        already_deployed, configs = check_deployments([node1, node2], False, {})
        self.assertEqual(2, mock__check_deployed_nodes.call_count)
        self.assertCountEqual([], already_deployed)
        self.assertEqual(2, len(configs))
        self.assertEqual([node1.fqdn], configs[0]["nodes"])
        self.assertEqual([node2.fqdn], configs[1]["nodes"])


class TestToEnoslib(EnosTest):
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_non_duplicated_hosts(self, mock_api):
        mock_api.return_value = get_offline_client()
        provider = G5k(Configuration())
        network = mock.Mock()
        provider.sshable_hosts = [G5kHost("1.2.3.4", ["tag1", "tag2"], network)]

        roles, _ = provider._to_enoslib()
        self.assertEqual(
            id(roles["tag1"][0]),
            id(roles["tag2"][0]),
            "Host refs aren't duplicated in roles",
        )

    # FIXME XXX
    # This produces some side effect on the API
    # def test_non_duplicated_networks(self):
    #     provider = G5k(Configuration())
    #     network = mock.Mock()
    #     provider.networks = [G5kProdNetwork(["tag1", "tag2"], "id1" , "rennes")]

    #     _, networks = provider._to_enoslib()
    #     self.assertEqual(id(networks["tag1"][0]),
    #  id(networks["tag2"][0]),
    # "Host refs aren't duplicated in roles")
