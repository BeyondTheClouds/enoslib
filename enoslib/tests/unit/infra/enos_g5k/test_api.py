import mock
import os

from enoslib.infra.enos_g5k.api import Resources, DEFAULT_ENV_NAME
import enoslib.infra.enos_g5k.api as api
from enoslib.infra.enos_g5k import utils, g5k_api_utils
from enoslib.infra.enos_g5k.constants import PROD, KAVLAN
from enoslib.tests.unit import EnosTest


class TestGetNetwork(EnosTest):

    def test_no_concrete_network_yet(self):
        demand_networks = [{"type": PROD, "id": "network1"}]
        r = Resources({"resources": {"networks": demand_networks, "machines": []}})
        networks = r.get_networks()
        self.assertCountEqual([], networks)

    def test_concrete_network(self):
        concrete_net = g5k_api_utils.ConcreteVlan(site="nancy", vlan_id=1)
        expected_roles = ["mynetwork"]
        networks = [{
            "typlse": KAVLAN,
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

    def test_prod(self):
        site = "rennes"
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        r = Resources({
            "resources":{
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": PROD, "id": "network1", "site": site}]
            }
        })
        deployed = set(nodes)
        undeployed = set()
        api._check_deployed_nodes = mock.Mock(return_value=(undeployed, deployed))
        r.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        r.driver.deploy.assert_called_with(site, nodes, {"env_name": DEFAULT_ENV_NAME})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    def test_vlan(self):
        site = "rennes"
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        _c_network = g5k_api_utils.ConcreteVlan(vlan_id="4", site=site)
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": KAVLAN, "id": "network1", "_c_network": [_c_network], "site": "rennes"}]
            }
        })
        deployed = set(nodes)
        undeployed = set()

        api._check_deployed_nodes = mock.Mock(return_value=(undeployed, deployed))
        r.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        r.driver.deploy.assert_called_with(site, nodes, {"env_name": DEFAULT_ENV_NAME, "vlan": "4"})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    def test_2_deployements_with_undeployed(self):
        site = "rennes"
        nodes_foo = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        nodes_bar = ["barcluster-1.rennes.grid5000.fr", "barcluster-2.rennes.grid5000.fr"]

        _c_network_1 = g5k_api_utils.ConcreteProd(site=site)
        _c_network_2 = g5k_api_utils.ConcreteVlan(vlan_id="4", site="rennes")
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
                    {"type": PROD, "id": "network1", "_c_network": [_c_network_1], "site": "rennes"},
                    {"type": KAVLAN, "id": "network2", "_c_network": [_c_network_2], "site": "rennes"}]
            }
        })
        d_foo = set(["foocluster-1.rennes.grid5000.fr"])
        u_foo = set(nodes_foo) - d_foo
        d_bar = set(["barcluster-2.rennes.grid5000.fr"])
        u_bar = set(nodes_bar) - d_bar

        # we make the deployed check fail to force the deployment
        api._check_deployed_nodes = mock.Mock(side_effect=[([], []), ([], [])])
        r.driver.deploy = mock.Mock(side_effect=[(d_foo, u_foo), (d_bar, u_bar)])
        r.deploy()
        self.assertEqual(2, r.driver.deploy.call_count)
        self.assertCountEqual(d_foo, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(u_foo, r.c_resources["machines"][0]["_c_undeployed"])
        self.assertCountEqual(d_bar, r.c_resources["machines"][1]["_c_deployed"])
        self.assertCountEqual(u_bar, r.c_resources["machines"][1]["_c_undeployed"])


    def test_dont_deployed_if_check_deployed_pass(self):
        site = "rennes"
        nodes = ["foocluster-1.rennes.grid5000.fr", "foocluster-2.rennes.grid5000.fr"]
        _c_network = g5k_api_utils.ConcreteVlan(vlan_id="4", site=site)
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": KAVLAN, "id": "network1", "_c_network": [_c_network], "site": "rennes"}]
            }
        })
        deployed = set(nodes)
        undeployed = set()

        api._check_deployed_nodes = mock.Mock(return_value=(deployed, undeployed))
        r.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()

        r.driver.deploy.assert_not_called()
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])
