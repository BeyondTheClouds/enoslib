import ipaddress
from typing import Dict
import mock

from enoslib.infra.enos_g5k.provider import (
    G5k,
    G5kHost,
    G5kProdNetwork,
    G5kVlanNetwork,
    G5kSubnetNetwork,
)

from enoslib.infra.enos_g5k.objects import (
    G5kEnosProd4Network,
    G5kEnosProd6Network,
    G5kEnosVlan4Network,
    G5kEnosVlan6Network,
    G5kEnosSubnetNetwork,
)

from enoslib.infra.enos_g5k.constants import (
    DEFAULT_ENV_NAME,
    DEFAULT_SSH_KEYFILE,
    KAVLAN,
    PROD,
)
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    Configuration,
    NetworkConfiguration,
)
from enoslib.tests.unit import EnosTest


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
        enos_network = G5kEnosProd4Network(enos_prod, "172.16.0.254", "172.16.0.25")
        self.assertFalse(enos_network.has_free_ips)
        self.assertCountEqual([], list(enos_network.free_ips))
        self.assertFalse(enos_network.has_free_macs)
        self.assertCountEqual([], list(enos_network.free_macs))

    def test_production6(self):
        enos_prod = ipaddress.ip_network("2001:660:4406:07::/64")
        enos_network = G5kEnosProd6Network(enos_prod, "::1", "::2")
        self.assertFalse(enos_network.has_free_ips)
        self.assertCountEqual([], list(enos_network.free_ips))
        self.assertFalse(enos_network.has_free_macs)
        self.assertCountEqual([], list(enos_network.free_macs))

    def test_kavlan(self):
        enos_kavlan = ipaddress.ip_network("10.24.0.0/18")
        enos_kavlan = G5kEnosVlan4Network(
            enos_kavlan, "172.16.0.254", "172.16.0.25", "4"
        )
        self.assertTrue(enos_kavlan.has_free_ips)
        # There should be a lot of ips available in the worse case
        # (/20 network == local vlan) => some /24 contiguous subnet
        self.assertTrue(len(list(enos_kavlan.free_ips)) > 3000)
        # not clear about macs, so we kept them empty
        self.assertFalse(enos_kavlan.has_free_macs)

    def test_kavlan6(self):
        enos_kavlan = ipaddress.ip_network("2001:660:4406:0790::/64")
        enos_kavlan = G5kEnosVlan6Network(enos_kavlan, "1::", "2::", 4)
        self.assertTrue(enos_kavlan.has_free_ips)
        # There should be a lot of ips available in the worse case
        # (/20 network == local vlan) => some /24 contiguous subnet
        it_ips = enos_kavlan.free_ips
        # let's get some ips
        ips = []
        for i in range(3000):
            ips.append(next(it_ips))
        self.assertEqual(3000, len(ips))
        # not clear about macs, so we kept them empty
        self.assertFalse(enos_kavlan.has_free_macs)

    def test_subnet(self):
        enos_subnet = ipaddress.ip_network("10.140.0.0/22")
        enos_subnet = G5kEnosSubnetNetwork(enos_subnet, "172.16.42.254", "172.16.42.25")
        self.assertTrue(enos_subnet.has_free_ips)
        # we get rid of the first and last address of the /22
        # which leaves us with 1022 addresses
        self.assertEqual(1022, len(list(enos_subnet.free_ips)))
        self.assertTrue(enos_subnet.has_free_macs)
        self.assertEqual(1022, len(list(enos_subnet.free_macs)))


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
    def build_provider(self, conf: Dict = None):
        if conf is None:
            conf = {}
        site = "rennes"
        oar_nodes = [
            "foocluster-1.rennes.grid5000.fr",
            "foocluster-2.rennes.grid5000.fr",
        ]

        # conf
        network_config = NetworkConfiguration(id="network1", type=PROD, site=site)
        # concrete
        g5k_networks = [G5kProdNetwork(["roles1"], "id1", site)]

        # conf
        cluster_config = ClusterConfiguration(
            site="rennes", primary_network=network_config
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

    def build_complex_provider(self, conf: Dict = None):

        if conf is None:
            conf = {}
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
            site="rennes", primary_network=network_1
        )
        cluster_config_2 = ClusterConfiguration(
            site="rennes", primary_network=network_2
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
        p, site, oar_nodes = self.build_provider()
        # mimic a successful deployment
        deployed = [h.fqdn for h in p.hosts]
        undeployed = []
        # no nodes has been deployed initially
        p._check_deployed_nodes = mock.Mock(return_value=(undeployed, deployed))
        p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        p.deploy()

        p.driver.deploy.assert_called_with(
            site,
            deployed,
            {"environment": DEFAULT_ENV_NAME, "key": DEFAULT_SSH_KEYFILE},
        )
        self.assertCountEqual(p.hosts, p.deployed)
        self.assertCountEqual(undeployed, p.undeployed)

    def test_prod_alt_key(self):
        p, site, oar_nodes = self.build_provider(dict(key="test_key"))
        # mimic a successful deployment
        deployed = [h.fqdn for h in p.hosts]
        undeployed = []
        # no nodes has been deployed initially
        p._check_deployed_nodes = mock.Mock(return_value=(undeployed, deployed))
        p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        p.deploy()

        p.driver.deploy.assert_called_with(
            site, deployed, {"environment": DEFAULT_ENV_NAME, "key": "test_key"}
        )
        self.assertCountEqual(p.hosts, p.deployed)
        self.assertCountEqual(undeployed, p.undeployed)

    def test_dont_deploy_if_check_deployed_pass(self):
        p, site, oar_nodes = self.build_provider()
        # mimic a successful deployment
        deployed = [h.fqdn for h in p.hosts]
        undeployed = []
        # no nodes has been deployed initially
        p._check_deployed_nodes = mock.Mock(return_value=(deployed, undeployed))
        p.driver.deploy = mock.Mock(return_value=(deployed, undeployed))
        p.deploy()

        p.driver.deploy.assert_not_called()
        self.assertCountEqual(p.hosts, p.deployed)
        self.assertCountEqual([], p.undeployed)

    def test_1_deployments_with_undeployed(self):
        p, site, oar_nodes = self.build_provider()
        # mimic a unsuccessful deployment
        deployed = []
        undeployed = [h.fqdn for h in p.hosts]

        p._check_deployed_nodes = mock.Mock(side_effect=[(deployed, undeployed)])
        p.driver.deploy = mock.Mock(side_effect=[(deployed, undeployed)])
        p.deploy()

        self.assertEqual(1, p.driver.deploy.call_count)
        self.assertCountEqual([], p.deployed)
        self.assertCountEqual(p.hosts, p.undeployed)

    def test_2_primary_network_one_vlan_ko(self):
        p, oar_nodes_1, oar_nodes_2, _ = self.build_complex_provider()

        p._check_deployed_nodes = mock.Mock(
            side_effect=[(set(), oar_nodes_1), (set(), oar_nodes_2)]
        )
        p.driver.deploy = mock.Mock(
            side_effect=[(set(), oar_nodes_1), (set(), oar_nodes_2)]
        )
        p.deploy()

        self.assertEqual(2, p.driver.deploy.call_count)

    def test_2_primary_network_one_vlan_ok(self):
        p, oar_nodes_1, oar_nodes_2, vlan = self.build_complex_provider()

        p._check_deployed_nodes = mock.Mock(
            side_effect=[(set(), oar_nodes_1), (set(), oar_nodes_2)]
        )
        p.driver.deploy = mock.Mock(
            side_effect=[(oar_nodes_1, set()), (oar_nodes_2, set())]
        )
        p.deploy()

        self.assertEqual(2, p.driver.deploy.call_count)
        # check that the names is ok
        names = [n[1] for n in vlan.translate(oar_nodes_2)]
        self.assertCountEqual([h.ssh_address for h in p.hosts], oar_nodes_1 + names)
