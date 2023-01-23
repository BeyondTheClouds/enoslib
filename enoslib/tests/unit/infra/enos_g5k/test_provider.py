import ipaddress
from collections import namedtuple
from typing import Dict, List, Optional
from unittest import mock

from enoslib.api import STATUS_FAILED, STATUS_OK, CommandResult, Results
from enoslib.errors import NegativeWalltime
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    Configuration,
    NetworkConfiguration,
)
from enoslib.infra.enos_g5k.constants import (
    DEFAULT_SSH_KEYFILE,
    KAVLAN,
    NETWORK_ROLE_PROD,
    PROD,
)
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
)
from enoslib.objects import Host
from enoslib.tests.unit import EnosTest


def get_offline_client():
    """Build on offline client.

    Allow to run (network isolated) tests against the reference API.
    """
    import json
    from pathlib import Path

    from grid5000 import Grid5000Offline

    data = json.loads((Path(__file__).parent / "reference.json").read_text())
    api = Grid5000Offline(data)
    # Allows the use of get_api_username()
    api.username = "dummy"
    return api


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


class TestDeploy(EnosTest):
    def build_provider(self, conf: Optional[Dict] = None):
        if conf is None:
            conf = {}
        site = "rennes"
        oar_nodes = [
            "foocluster-1.rennes.grid5000.fr",
            "foocluster-2.rennes.grid5000.fr",
        ]

        # conf
        network_config = NetworkConfiguration(
            id="network1", type=PROD, site=site, roles=["roles1"]
        )
        # concrete
        g5k_networks = [G5kProdNetwork(["roles1"], "id1", site)]

        # conf
        cluster_config = ClusterConfiguration(
            cluster="foocluster",
            site="rennes",
            primary_network=network_config,
        )

        provider_config = (
            Configuration()
            .from_settings(**conf)
            .add_machine_conf(cluster_config)
            .add_network_conf(network_config)
        )
        # build a provider
        p = G5k(provider_config)

        # mimic a reservation
        p.hosts = [
            G5kHost(oar_nodes[0], ["r1"], g5k_networks[0], []),
            G5kHost(oar_nodes[1], ["r1"], g5k_networks[0], []),
        ]

        return p, site, oar_nodes

    def build_complex_provider(self, conf: Optional[Dict] = None):

        if conf is None:
            conf = {"job_type": ["deploy"], "env_name": "debian11-min"}
        site = "rennes"
        oar_nodes_1 = [
            "foocluster-1.rennes.grid5000.fr",
            "foocluster-2.rennes.grid5000.fr",
        ]
        oar_nodes_2 = [
            "barcluster-1.rennes.grid5000.fr",
            "barcluster-2.rennes.grid5000.fr",
        ]

        network_1 = NetworkConfiguration(id="network_1", type=PROD, site=site)
        network_2 = NetworkConfiguration(id="network_2", type=KAVLAN, site=site)

        cluster_config_1 = ClusterConfiguration(
            cluster="foocluster", site="rennes", primary_network=network_1
        )
        cluster_config_2 = ClusterConfiguration(
            cluster="barcluster", site="rennes", primary_network=network_2
        )

        oar_network_1 = G5kProdNetwork(["roles1"], "id1", "rennes")
        oar_network_2 = G5kVlanNetwork(["roles1"], "id2", "rennes", "4")

        provider_config = (
            Configuration()
            .from_settings(**conf)
            .add_machine_conf(cluster_config_1)
            .add_machine_conf(cluster_config_2)
            .add_network_conf(network_1)
            .add_network_conf(network_2)
        )
        # build a provider
        p = G5k(provider_config)

        # mimic a reservation
        p.hosts = [
            G5kHost(oar_nodes_1[0], ["r1"], oar_network_1, []),
            G5kHost(oar_nodes_1[1], ["r1"], oar_network_1, []),
            G5kHost(oar_nodes_2[0], ["r1"], oar_network_2, []),
            G5kHost(oar_nodes_2[1], ["r1"], oar_network_2, []),
        ]

        return p, oar_nodes_1, oar_nodes_2, oar_network_2

    def test_prod(self):
        conf = {"env_name": "debian11-nfs", "job_type": ["deploy"]}
        p, site, oar_nodes = self.build_provider(conf=conf)
        # mimic a successful deployment
        deployed: List = [h.fqdn for h in p.hosts]
        undeployed: List = []
        # no nodes has been deployed initially
        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as mock_check_deployed_nodes:
            mock_check_deployed_nodes.return_value = (undeployed, deployed)
            p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
            p.deploy()

        p.driver.deploy.assert_called_with(
            site,
            deployed,
            {"environment": "debian11-nfs", "key": DEFAULT_SSH_KEYFILE},
        )
        # self.assertCountEqual(actual_deployed, p.hosts)
        self.assertCountEqual([], p.undeployed)
        self.assertCountEqual(p.sshable_hosts, p.deployed)

    def test_prod_alt_key(self):
        conf = {"env_name": "debian11-nfs", "job_type": ["deploy"], "key": "test_key"}
        p, site, oar_nodes = self.build_provider(conf=conf)
        # mimic a successful deployment
        deployed: List = [h.fqdn for h in p.hosts]
        undeployed: List = []
        # no nodes has been deployed initially
        p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as mock_check_deployed_nodes:
            mock_check_deployed_nodes.return_value = (undeployed, deployed)
            p.deploy()

        p.driver.deploy.assert_called_with(
            site, deployed, {"environment": "debian11-nfs", "key": "test_key"}
        )
        # self.assertCountEqual(p.hosts, p.deployed)
        self.assertCountEqual([], p.undeployed)
        self.assertCountEqual(p.sshable_hosts, p.deployed)

    def test_dont_deploy_if_check_deployed_pass(self):
        p, site, oar_nodes = self.build_provider()
        # mimic a successful deployment
        deployed: List = [h.fqdn for h in p.hosts]
        undeployed: List = []
        # all nodes are already deployed
        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as mock_check_deployed_nodes:
            mock_check_deployed_nodes.return_value = (deployed, undeployed)
            p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
            actual_deployed, _ = p.deploy()

        p.driver.deploy.assert_not_called()
        # self.assertCountEqual(p.hosts, p.deployed)
        self.assertCountEqual([], p.undeployed)
        self.assertCountEqual(actual_deployed, p.sshable_hosts)

    def test_1_deployments_with_undeployed(self):
        p, site, oar_nodes = self.build_provider()
        # mimic a unsuccessful deployment
        deployed: List = []
        undeployed: List = [h.fqdn for h in p.hosts]

        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as mock_check_deployed_nodes:
            mock_check_deployed_nodes.return_value = (deployed, undeployed)
            p.driver.deploy = mock.Mock(side_effect=[(deployed, undeployed)])
            p.deploy()

        self.assertEqual(1, p.driver.deploy.call_count)
        self.assertCountEqual([], p.deployed)
        self.assertCountEqual([], p.sshable_hosts)
        self.assertCountEqual(p.undeployed, p.hosts)

    def test_2_primary_network_one_vlan_ko(self):
        p, oar_nodes_1, oar_nodes_2, _ = self.build_complex_provider()

        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as patch_check_deployed_nodes:
            patch_check_deployed_nodes.side_effect = [
                (set(), oar_nodes_1),
                (set(), oar_nodes_2),
            ]
            p.driver.deploy = mock.Mock(
                side_effect=[(set(), oar_nodes_1), (set(), oar_nodes_2)]
            )
            p.deploy()

        self.assertEqual(2, p.driver.deploy.call_count)

    def test_2_primary_network_one_vlan_ok(self):
        p, oar_nodes_1, oar_nodes_2, vlan = self.build_complex_provider()

        with mock.patch(
            "enoslib.infra.enos_g5k.provider._check_deployed_nodes"
        ) as patch_check_deployed_nodes:
            patch_check_deployed_nodes.side_effect = [
                (set(), oar_nodes_1),
                (set(), oar_nodes_2),
            ]
            p.driver.deploy = mock.Mock(
                side_effect=[(oar_nodes_1, set()), (oar_nodes_2, set())]
            )
            p.deploy()

        self.assertEqual(2, p.driver.deploy.call_count)
        # check that the names is ok
        names = [n[1] for n in vlan.translate(oar_nodes_2)]
        self.assertCountEqual([h.ssh_address for h in p.hosts], oar_nodes_1 + names)

    @mock.patch("enoslib.infra.enos_g5k.driver.grid_reload_jobs_from_name")
    @mock.patch("enoslib.infra.enos_g5k.driver.wait_for_jobs")
    @mock.patch("enoslib.infra.enos_g5k.driver.grid_deploy")
    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    @mock.patch("enoslib.infra.enos_g5k.provider._run_dhcp")
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_multisite_deploy_prod(
        self,
        mock_api,
        mock_run_dhcp,
        mock_check_deployed_nodes,
        mock_grid_deploy,
        mock_wait_for_jobs,
        mock_grid_reload_jobs_from_name,
    ):

        cluster_config_nancy = ClusterConfiguration(
            cluster="grisou", site="nancy", roles=["role1"], nodes=2
        )
        cluster_config_rennes = ClusterConfiguration(
            cluster="paravance", site="rennes", roles=["role1"], nodes=2
        )

        provider_config = (
            Configuration.from_settings(job_type=["deploy"], env_name="debian11-nfs")
            .add_machine_conf(cluster_config_nancy)
            .add_machine_conf(cluster_config_rennes)
        )

        # build a provider
        p = G5k(provider_config)

        # we bypass the reserve phase / wait phase
        p.reserve = mock.MagicMock()  # type: ignore
        p.reserve.return_value = None

        p.mirror_state = mock.MagicMock()  # type: ignore
        p.mirror_state.return_value = None  # type: ignore

        # mimicking a grid5000.Job object (we only need to access the status,
        # assigned_resources)
        Job = namedtuple(
            "Job", ["status", "site", "assigned_nodes", "resources_by_type"]
        )

        oar_nodes_rennes = [
            "paravance-1.rennes.grid5000.fr",
            "paravance-2.rennes.grid5000.fr",
        ]
        oar_nodes_nancy = ["grisou-1.nancy.grid5000.fr", "grisou-2.nancy.grid5000.fr"]
        mock_grid_reload_jobs_from_name.return_value = [
            Job("Running", "nancy", oar_nodes_nancy, {}),
            Job("Running", "rennes", oar_nodes_rennes, {}),
        ]
        mock_wait_for_jobs.return_value = None

        # not called (see below)
        mock_grid_deploy.side_effect = [(oar_nodes_nancy, []), (oar_nodes_rennes, [])]

        # called twice one per site
        mock_check_deployed_nodes.side_effect = [
            (oar_nodes_nancy, []),
            (oar_nodes_rennes, []),
        ]
        mock_run_dhcp.return_value = None

        mock_api.return_value = get_offline_client()

        roles, networks = p.init()

        mock_grid_deploy.assert_not_called()
        self.assertEqual(2, mock_check_deployed_nodes.call_count)
        # two hosts are equal if they target the same machine with the same user
        extra = {"gateway": "access.grid5000.fr", "gateway_user": "dummy"}
        self.assertCountEqual(
            [
                Host(h, user="root", extra=extra)
                for h in oar_nodes_nancy + oar_nodes_rennes
            ],
            roles["role1"],
        )
        self.assertEqual(4, len(networks[NETWORK_ROLE_PROD]))

    @mock.patch("enoslib.infra.enos_g5k.driver.grid_reload_jobs_from_name")
    @mock.patch("enoslib.infra.enos_g5k.driver.wait_for_jobs")
    @mock.patch("enoslib.infra.enos_g5k.driver.grid_deploy")
    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    @mock.patch("enoslib.infra.enos_g5k.provider._run_dhcp")
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_multisite_deploy_kavlan(
        self,
        mock_api,
        mock_run_dhcp,
        mock_check_deployed_nodes,
        mock_grid_deploy,
        mock_wait_for_jobs,
        mock_grid_reload_jobs_from_name,
    ):

        kavlan_rennes = NetworkConfiguration(
            roles=["role1"], type="kavlan-global", site="rennes"
        )

        cluster_config_nancy = ClusterConfiguration(
            cluster="grisou",
            site="nancy",
            roles=["role1"],
            nodes=2,
            primary_network=kavlan_rennes,
        )
        cluster_config_rennes = ClusterConfiguration(
            cluster="paravance",
            site="rennes",
            roles=["role1"],
            nodes=2,
            primary_network=kavlan_rennes,
        )

        provider_config = (
            Configuration.from_settings(job_type=["deploy"], env_name="debian11-nfs")
            .add_machine_conf(cluster_config_nancy)
            .add_machine_conf(cluster_config_rennes)
            .add_network_conf(kavlan_rennes)
        )

        # build a provider
        p: G5k = G5k(provider_config)

        # we bypass the reserve phase / wait phase
        p.reserve = mock.MagicMock()  # type: ignore
        p.reserve.return_value = None

        p.mirror_state = mock.MagicMock()  # type: ignore
        p.mirror_state.return_value = None  # type: ignore

        # mimicking a grid5000.Job object (we only need to access the status,
        # assigned_resources)
        Job = namedtuple(
            "Job", ["status", "site", "assigned_nodes", "resources_by_type"]
        )

        oar_nodes_rennes = [
            "paravance-1.rennes.grid5000.fr",
            "paravance-2.rennes.grid5000.fr",
        ]
        oar_nodes_nancy = ["grisou-1.nancy.grid5000.fr", "grisou-2.nancy.grid5000.fr"]
        mock_grid_reload_jobs_from_name.return_value = [
            Job("Running", "nancy", oar_nodes_nancy, {}),
            Job("Running", "rennes", oar_nodes_rennes, {"vlans": ["16"]}),
        ]
        mock_wait_for_jobs.return_value = None

        # not called (see below)
        mock_grid_deploy.side_effect = [(oar_nodes_nancy, []), (oar_nodes_rennes, [])]

        # called twice one per site
        mock_check_deployed_nodes.side_effect = [
            (oar_nodes_nancy, []),
            (oar_nodes_rennes, []),
        ]
        mock_run_dhcp.return_value = None

        mock_api.return_value = get_offline_client()

        roles, networks = p.init()

        mock_grid_deploy.assert_not_called()
        self.assertEqual(2, mock_check_deployed_nodes.call_count)
        kavlan_nodes = [
            "paravance-1-kavlan-16.rennes.grid5000.fr",
            "paravance-2-kavlan-16.rennes.grid5000.fr",
            "grisou-1-kavlan-16.nancy.grid5000.fr",
            "grisou-2-kavlan-16.nancy.grid5000.fr",
        ]
        extra = {"gateway": "access.grid5000.fr", "gateway_user": "dummy"}
        self.assertCountEqual(
            [Host(h, user="root", extra=extra) for h in kavlan_nodes], roles["role1"]
        )
        # 1 vlan ipv4 + its ipv6 counterpart
        self.assertEqual(2, len(networks["role1"]))

    @mock.patch("enoslib.infra.enos_g5k.driver.grid_reload_jobs_from_name")
    @mock.patch("enoslib.infra.enos_g5k.driver.wait_for_jobs")
    @mock.patch("enoslib.infra.enos_g5k.driver.grid_deploy")
    @mock.patch("enoslib.infra.enos_g5k.provider._check_deployed_nodes")
    @mock.patch("enoslib.infra.enos_g5k.provider._run_dhcp")
    @mock.patch("enoslib.infra.enos_g5k.objects.set_nodes_vlan")
    @mock.patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_multisite_deploy_kavlan_secondary(
        self,
        mock_api,
        mock_set_nodes_vlan,
        mock_run_dhcp,
        mock_check_deployed_nodes,
        mock_grid_deploy,
        mock_wait_for_jobs,
        mock_grid_reload_jobs_from_name,
    ):

        kavlan_rennes = NetworkConfiguration(
            roles=["role1"], type="kavlan-global", site="rennes"
        )

        cluster_config_nancy = ClusterConfiguration(
            cluster="grisou",
            site="nancy",
            roles=["role1"],
            nodes=2,
            secondary_networks=[kavlan_rennes],
        )
        cluster_config_rennes = ClusterConfiguration(
            cluster="paravance",
            site="rennes",
            roles=["role1"],
            nodes=2,
            secondary_networks=[kavlan_rennes],
        )

        provider_config = (
            Configuration.from_settings(job_type=["deploy"], env_name="debian11-nfs")
            .add_machine_conf(cluster_config_nancy)
            .add_machine_conf(cluster_config_rennes)
            .add_network_conf(kavlan_rennes)
        )

        # build a provider
        p = G5k(provider_config)

        # we bypass the reserve phase / wait phase
        p.reserve = mock.MagicMock()  # type: ignore
        p.reserve.return_value = None

        # mimicking a grid5000.Job object (we only need to access the status,
        # assigned_resources)
        Job = namedtuple(
            "Job", ["status", "site", "assigned_nodes", "resources_by_type"]
        )

        oar_nodes_rennes = [
            "paravance-1.rennes.grid5000.fr",
            "paravance-2.rennes.grid5000.fr",
        ]
        oar_nodes_nancy = ["grisou-1.nancy.grid5000.fr", "grisou-2.nancy.grid5000.fr"]
        mock_grid_reload_jobs_from_name.return_value = [
            Job("Running", "nancy", oar_nodes_nancy, {}),
            Job("Running", "rennes", oar_nodes_rennes, {"vlans": ["16"]}),
        ]
        mock_wait_for_jobs.return_value = None

        # not called (see below)
        mock_grid_deploy.side_effect = [(oar_nodes_nancy, []), (oar_nodes_rennes, [])]

        # called twice one per site
        mock_check_deployed_nodes.side_effect = [
            (oar_nodes_nancy, []),
            (oar_nodes_rennes, []),
        ]
        mock_run_dhcp.return_value = None

        mock_api.return_value = get_offline_client()

        roles, networks = p.init()

        mock_grid_deploy.assert_not_called()
        self.assertEqual(2, mock_check_deployed_nodes.call_count)
        kavlan_nodes = [
            "paravance-1.rennes.grid5000.fr",
            "paravance-2.rennes.grid5000.fr",
            "grisou-1.nancy.grid5000.fr",
            "grisou-2.nancy.grid5000.fr",
        ]
        self.maxDiff = None
        extra = {"gateway": "access.grid5000.fr", "gateway_user": "dummy"}
        self.assertCountEqual(
            [Host(h, user="root", extra=extra) for h in kavlan_nodes], roles["role1"]
        )

        mock_set_nodes_vlan.assert_any_call(
            ["paravance-1.rennes.grid5000.fr"], "eth1", "16"
        )
        mock_set_nodes_vlan.assert_any_call(
            ["paravance-2.rennes.grid5000.fr"], "eth1", "16"
        )
        mock_set_nodes_vlan.assert_any_call(
            ["grisou-1.nancy.grid5000.fr"], "eth1", "16"
        )
        mock_set_nodes_vlan.assert_any_call(
            ["grisou-2.nancy.grid5000.fr"], "eth1", "16"
        )
        # 1 vlan ipv4 + its ipv6 counterpart
        self.assertEqual(2, len(networks["role1"]))


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
        deployed, undeployed = _check_deployed_nodes(
            net,
            [
                G5kHost("plip-1.rennes.grid5000.fr", [], net),
                G5kHost("plip-2.rennes.grid5000.fr", [], net),
            ],
        )
        self.assertCountEqual(["plip-1.rennes.grid5000.fr"], deployed)
        self.assertCountEqual(["plip-2.rennes.grid5000.fr"], undeployed)


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
