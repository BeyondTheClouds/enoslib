import ipaddress
from typing import List, Optional
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
    _check_env_name_and_version,
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
        mock_submit = mock.MagicMock()
        mock_submit.return_value = {
            nodes[0]: {"status": "success", "message": "dummy"},
            nodes[1]: {"status": "success", "message": "dummy"},
        }

        mock_vlan = mock.MagicMock()
        mock_vlan.nodes.submit = mock_submit

        mock_site = mock.MagicMock()
        mock_site.vlans = {vlan_id: mock_vlan}

        kavlan_api = mock.MagicMock()
        kavlan_api.sites = {site: mock_site}

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
        mock_submit = mock.MagicMock()
        mock_submit.return_value = {
            nodes[0]: {"status": "unchanged", "message": "dummy"},
            nodes[1]: {"status": "success", "message": "dummy"},
        }

        mock_vlan = mock.MagicMock()
        mock_vlan.nodes.submit = mock_submit

        mock_site = mock.MagicMock()
        mock_site.vlans = {vlan_id: mock_vlan}

        kavlan_api = mock.MagicMock()
        kavlan_api.sites = {site: mock_site}

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
        mock_submit = mock.MagicMock()
        mock_submit.return_value = {
            nodes[0]: {"status": "failure", "message": "error"},
            nodes[1]: {"status": "success", "message": "dummy"},
        }

        mock_vlan = mock.MagicMock()
        mock_vlan.nodes.submit = mock_submit

        mock_site = mock.MagicMock()
        mock_site.vlans = {vlan_id: mock_vlan}

        kavlan_api = mock.MagicMock()
        kavlan_api.sites = {site: mock_site}

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


@mock.patch("enoslib.infra.enos_g5k.provider.run")
class TestCheckEnvNameAndVersion(EnosTest):

    def _get_mocked_host(self):
        host = mock.MagicMock()
        host.to_enoslib.return_value = mock.MagicMock()
        return host

    def _get_mocked_ansible_result(self, host_name: str, scenario: str):
        res = mock.MagicMock()
        res.host = host_name

        if scenario == "success":
            res.payload = {"rc": 0, "stdout_lines": ["ubuntu2404-x64-min-2024042614"]}
        elif scenario == "empty_stdout":
            res.payload = {"rc": 0, "stdout_lines": []}
        elif scenario == "fail":
            res.payload = {"rc": 1, "stderr_lines": ["Permission denied"]}
        elif scenario == "no_rc":
            res.payload = {
                "unreachable": True,
                "msg": "Failed to connect to the host via ssh",
            }

        return res

    def test_successful_os_retrieving(self, mock_run):

        sshable_hosts = [self._get_mocked_host(), self._get_mocked_host()]

        mock_run.return_value = [
            self._get_mocked_ansible_result(f"node-{i}", "success") for i in range(1, 3)
        ]

        parsed_results = _check_env_name_and_version(sshable_hosts)

        self.assertEqual(len(parsed_results), 2)
        self.assertEqual(parsed_results[0], "ubuntu2404-x64-min-2024042614")
        self.assertEqual(parsed_results[1], "ubuntu2404-x64-min-2024042614")

    def test_empty_standard_output(self, mock_run):
        sshable_hosts = [self._get_mocked_host(), self._get_mocked_host()]

        mock_run.return_value = [
            self._get_mocked_ansible_result(f"node-{i}", "empty_stdout")
            for i in range(1, 3)
        ]

        parsed_results = _check_env_name_and_version(sshable_hosts)

        self.assertEqual(len(parsed_results), 0)
        self.assertEqual(parsed_results, [])

    def test_failed_os_retrieving_with_rc(self, mock_run):
        sshable_hosts = [self._get_mocked_host(), self._get_mocked_host()]

        mock_run.return_value = [
            self._get_mocked_ansible_result(f"node-{i}", "fail") for i in range(1, 3)
        ]

        parsed_results = _check_env_name_and_version(sshable_hosts)

        self.assertEqual(len(parsed_results), 0)
        self.assertEqual(parsed_results, [])

    def test_failed_os_retrieving_without_rc(self, mock_run):
        sshable_hosts = [self._get_mocked_host(), self._get_mocked_host()]

        mock_run.return_value = [
            self._get_mocked_ansible_result(f"node-{i}", "no_rc") for i in range(1, 3)
        ]

        parsed_results = _check_env_name_and_version(sshable_hosts)

        self.assertEqual(len(parsed_results), 0)
        self.assertEqual(parsed_results, [])

    def test_heterogeneous_ansible_results(self, mock_run):
        sshable_hosts = [self._get_mocked_host() for _ in range(4)]

        mock_run.return_value = [
            self._get_mocked_ansible_result("node-1", "success"),
            self._get_mocked_ansible_result("node-2", "empty_stdout"),
            self._get_mocked_ansible_result("node-3", "fail"),
            self._get_mocked_ansible_result("node-4", "no_rc"),
        ]

        parsed_results = _check_env_name_and_version(sshable_hosts)

        self.assertEqual(len(parsed_results), 1)
        self.assertEqual(parsed_results[0], "ubuntu2404-x64-min-2024042614")


class TestVerifyEnvironmentConsistency(EnosTest):

    def _get_mocked_provider(self, env_name, env_version, hosts_quantity: int = 0):

        configuration = Configuration.from_settings(
            env_name=env_name,
            env_version=env_version,
            job_type=["deploy"],
        )
        provider = G5k(configuration)

        if hosts_quantity:
            provider.sshable_hosts = [mock.MagicMock() for _ in range(hosts_quantity)]

        return provider

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_no_os_retrieved(self, mock_check_env):

        provider = self._get_mocked_provider(
            env_name="ubuntu2404-min", env_version=None, hosts_quantity=1
        )

        mock_check_env.return_value = []

        self.assertEqual(False, provider._verify_environment_consistency())

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_env_name_and_version_os_retrieved_match(self, mock_check_env):

        provider = self._get_mocked_provider(
            env_name="ubuntu2404-min", env_version=2025082609, hosts_quantity=1
        )

        mock_check_env.return_value = ["ubuntu2404-x64-min-2025082609"]

        self.assertEqual(True, provider._verify_environment_consistency())

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_env_name_and_version_os_retrieved_no_match(self, mock_check_env):

        provider = self._get_mocked_provider(
            env_name="ubuntu2404-min", env_version=2025082609, hosts_quantity=1
        )

        mock_check_env.return_value = ["ubuntu2404-x64-min-2024042614"]

        self.assertEqual(False, provider._verify_environment_consistency())

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_env_name_no_env_version_os_retrieved_match(self, mock_check_env):
        provider = self._get_mocked_provider(
            env_name="ubuntu2404-min", env_version=None, hosts_quantity=1
        )

        mock_check_env.return_value = ["ubuntu2404-x64-min-2025082609"]

        self.assertEqual(True, provider._verify_environment_consistency())

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_env_name_no_env_version_os_retrieved_no_match(self, mock_check_env):
        provider = self._get_mocked_provider(
            env_name="debian11-min", env_version=None, hosts_quantity=1
        )

        mock_check_env.return_value = ["ubuntu2404-x64-min-2024042614"]

        self.assertEqual(False, provider._verify_environment_consistency())

    @mock.patch("enoslib.infra.enos_g5k.provider._check_env_name_and_version")
    def test_heterogeneous_environments_retrieved(self, mock_check_env):
        provider = self._get_mocked_provider(
            env_name="ubuntu2404-min", env_version=2025082609, hosts_quantity=2
        )

        mock_check_env.return_value = [
            "ubuntu2404-x64-min-2025082609",
            "ubuntu2404-x64-std-2024042614",
        ]

        self.assertEqual(False, provider._verify_environment_consistency())


class TestLaunch(EnosTest):

    def _get_mocked_provider(
        self,
        has_deploy_job_type: bool,
        env_name: Optional[str] = "ubuntu2404-min",
        env_version: Optional[int] = 2025082609,
    ):

        configuration = Configuration.from_settings(
            env_name=env_name,
            env_version=env_version,
            job_type=["deploy"] if has_deploy_job_type else [],
        )
        provider = G5k(configuration)

        # Provider internal methods mocking
        for method in [
            "reserve",
            "wait",
        ]:
            setattr(provider, method, mock.MagicMock())

        provider.driver = mock.MagicMock()
        provider.driver.resources.return_value = ([], [])

        return provider

    @mock.patch.object(G5k, "grant_root_access")
    def test_launch_no_deploy(self, mock_grant_root_access):

        provider = self._get_mocked_provider(
            has_deploy_job_type=False,
            env_name=None,
            env_version=None,
        )
        provider.launch()
        mock_grant_root_access.assert_called_once()

    @mock.patch.object(G5k, "_verify_environment_consistency")
    @mock.patch.object(G5k, "deploy")
    @mock.patch.object(G5k, "wait_nodes")
    @mock.patch.object(G5k, "dhcp_networks")
    def test_launch_deploy_consistently_deployed(
        self,
        mock_dhcp_networks,
        mock_wait_nodes,
        mock_deploy,
        mock_verify_environment_consistency,
    ):
        provider = self._get_mocked_provider(has_deploy_job_type=True)
        mock_verify_environment_consistency.return_value = True

        provider.launch()

        mock_verify_environment_consistency.assert_called_once()
        mock_deploy.assert_not_called()
        mock_wait_nodes.assert_not_called()
        mock_dhcp_networks.assert_not_called()

    @mock.patch.object(G5k, "_verify_environment_consistency")
    @mock.patch.object(G5k, "deploy")
    @mock.patch.object(G5k, "wait_nodes")
    @mock.patch.object(G5k, "dhcp_networks")
    def test_launch_deploy_not_consistently_deployed(
        self,
        mock_dhcp_networks,
        mock_wait_nodes,
        mock_deploy,
        mock_verify_environment_consistency,
    ):
        provider = self._get_mocked_provider(has_deploy_job_type=True)
        mock_verify_environment_consistency.return_value = False

        provider.launch()
        mock_verify_environment_consistency.assert_called_once()
        self.assertTrue(provider.provider_conf.force_deploy)
        mock_deploy.assert_called_once()
        mock_wait_nodes.assert_called_once()
        mock_dhcp_networks.assert_called_once()

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
