import mock
import os

from enoslib.infra.enos_g5k.api import Resources, DEFAULT_ENV_NAME
from enoslib.infra.enos_g5k import utils
from enoslib.infra.enos_g5k.schema import PROD, KAVLAN
from enoslib.tests.unit import EnosTest


class TestGetNetwork(EnosTest):

    @mock.patch("enoslib.infra.enos_g5k.api._get_grid5000_client")
    def test_no_concrete_network_yet(self, mock_gk):
        demand_networks = [{"type": PROD, "id": "network1"}]
        r = Resources({"resources": {"networks": demand_networks, "machines": []}})
        networks = r.get_networks()
        self.assertCountEqual([], networks)

    @mock.patch("enoslib.infra.enos_g5k.api._get_grid5000_client")
    def test_concrete_network(self, mock_gk):
        concrete_net = utils.ConcreteVlan(site="nancy", vlan_id=1)
        expected_roles = ["mynetwork"]
        networks = [{
            "type": KAVLAN,
            "id": "network1",
            "roles": expected_roles,
            "_c_network": concrete_net}]
        # a bit hacky because _c_network will be deepcopied so the ref will change
        r = Resources({"resources": {"networks": networks, "machines": []}})
        networks = r.get_networks()
        self.assertEqual(1, len(networks))
        actual_roles, actual_net = networks[0]
        self.assertCountEqual(expected_roles, actual_roles)


class TestDeploy(EnosTest):

    @mock.patch("enoslib.infra.enos_g5k.api._get_grid5000_client")
    def test_prod(self, mock_gk):
        site = "rennes"
        nodes = ["foocluster-1", "foocluster-2"]
        r = Resources({
            "resources":{
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": PROD, "id": "network1", "site": site}]
            }
        })
        deployed = set(["foocluster-1", "foocluster-2"])
        undeployed = set()
        r.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        r.driver.deploy.assert_called_with(site, nodes, False, {"env_name": DEFAULT_ENV_NAME})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    @mock.patch("enoslib.infra.enos_g5k.api._get_grid5000_client")
    def test_vlan(self, mock_gk):
        site = "rennes"
        nodes = ["foocluster-1", "foocluster-2"]
        _c_network = utils.ConcreteVlan(vlan_id="4", site=site)
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": KAVLAN, "id": "network1", "_c_network": _c_network, "site": "rennes"}]
            }
        })
        deployed = set(["foocluster-1", "foocluster-2"])
        undeployed = set()

        r.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        r.driver.deploy.assert_called_with(site, nodes, False, {"env_name": DEFAULT_ENV_NAME, "vlan": "4"})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    @mock.patch("enoslib.infra.enos_g5k.api._get_grid5000_client")
    def test_2_deployements_with_undeployed(self, mock_gk):
        site = "rennes"
        nodes_foo = ["foocluster-1", "foocluster-2"]
        nodes_bar = ["barcluster-1", "barcluster-2"]

        _c_network_1 = utils.ConcreteProd(site=site)
        _c_network_2 = utils.ConcreteVlan(vlan_id="4", site="rennes")
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes_foo,
                    "primary_network": "network1"
                }, {
                    "_c_nodes" : nodes_bar,
                    "primary_network": "network2"
                }],
                "networks": [
                    {"type": PROD, "id": "network1", "_c_network": _c_network_1, "site": "rennes"},
                    {"type": KAVLAN, "id": "network2", "_c_network": _c_network_2, "site": "rennes"}]
            }
        })
        d_foo = set(["foocluster-1"])
        u_foo = set(nodes_foo) - d_foo
        d_bar = set(["barcluster-2"])
        u_bar = set(nodes_bar) - d_bar

        r.driver.deploy = mock.Mock(side_effect=[(d_foo, u_foo), (d_bar, u_bar)])
        r.deploy()
        self.assertEqual(2, r.driver.deploy.call_count)
        self.assertCountEqual(d_foo, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(u_foo, r.c_resources["machines"][0]["_c_undeployed"])
        self.assertCountEqual(d_bar, r.c_resources["machines"][1]["_c_deployed"])
        self.assertCountEqual(u_bar, r.c_resources["machines"][1]["_c_undeployed"])
