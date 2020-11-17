from typing import Dict
import mock

from enoslib.infra.enos_g5k.provider import G5k, G5kHost, G5kProdNetwork, G5kVlanNetwork

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
