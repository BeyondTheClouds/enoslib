from enoslib.infra.enos_g5k.api import Resources, DEFAULT_ENV_NAME
from enoslib.infra.enos_g5k import utils
from enoslib.infra.enos_g5k.schema import PROD, KAVLAN
import mock

from enoslib.tests.unit import EnosTest

class TestGetNetwork(EnosTest):

    def test_no_concrete_network_yet(self):
        expected_networks = [{"type": PROD, "id": "network1"}]
        r = Resources({"resources": {"networks": expected_networks, "machines": []}})
        networks = r.get_networks()
        self.assertCountEqual(expected_networks, networks)

    def test_concrete_network(self):
        networks = [{"type": KAVLAN, "id": "network1", "_c_network": {"site": "nancy", "vlan_id": 1}}]
        expected_networks = [{"type": KAVLAN, "id": "network1", "site": "nancy", "vlan_id": 1}]
        r = Resources({"resources": {"networks": networks, "machines": []}})
        networks = r.get_networks()
        self.assertCountEqual(expected_networks, networks)


class TestDeploy(EnosTest):

    def test_prod(self):
        nodes = ["foocluster-1", "foocluster-2"]
        r = Resources({
            "resources":{
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": PROD, "id": "network1"}]
            }
        })
        deployed = set(["foocluster-1", "foocluster-2"])
        undeployed = set()
        utils._deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        utils._deploy.assert_called_with(nodes, False, {"env_name": DEFAULT_ENV_NAME})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    def test_vlan(self):
        nodes = ["foocluster-1", "foocluster-2"]
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes,
                    "primary_network": "network1"
                }],
                "networks": [{"type": KAVLAN, "id": "network1", "_c_network": {"site": "rennes", "vlan_id": 4}}]
            }
        })
        deployed = set(["foocluster-1", "foocluster-2"])
        undeployed = set()
        utils._deploy = mock.Mock(return_value=(deployed, undeployed))
        r.deploy()
        utils._deploy.assert_called_with(nodes, False, {"env_name": DEFAULT_ENV_NAME, "vlan": 4})
        self.assertCountEqual(deployed, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(undeployed, r.c_resources["machines"][0]["_c_undeployed"])

    def test_2_deployements_with_undeployed(self):
        nodes_foo = ["foocluster-1", "foocluster-2"]
        nodes_bar = ["barcluster-1", "barcluster-2"]
        r = Resources({
            "resources": {
                "machines": [{
                    "_c_nodes": nodes_foo,
                    "primary_network": "network1"
                },{
                    "_c_nodes" : nodes_bar,
                    "primary_network": "network2"
                    }
                ],
                "networks": [
                    {"type": PROD, "id": "network1"},
                    {"type": KAVLAN, "id": "network2", "_c_network": {"site": "rennes", "vlan_id": 4}}]
            }
        })
        d_foo = set(["foocluster-1"])
        u_foo = set(nodes_foo) - d_foo
        d_bar = set(["barcluster-2"])
        u_bar = set(nodes_bar) - d_bar
        utils._deploy = mock.Mock(side_effect=[(d_foo, u_foo), (d_bar, u_bar)])
        r.deploy()
        self.assertEqual(2, utils._deploy.call_count)
        self.assertCountEqual(d_foo, r.c_resources["machines"][0]["_c_deployed"])
        self.assertCountEqual(u_foo, r.c_resources["machines"][0]["_c_undeployed"])
        self.assertCountEqual(d_bar, r.c_resources["machines"][1]["_c_deployed"])
        self.assertCountEqual(u_bar, r.c_resources["machines"][1]["_c_undeployed"])


