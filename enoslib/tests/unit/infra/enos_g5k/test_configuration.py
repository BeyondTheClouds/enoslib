from jsonschema.exceptions import ValidationError
from mock import patch
from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    Configuration,
    NetworkConfiguration,
    GroupConfiguration,
)
import enoslib.infra.enos_g5k.constants as constants

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionnary_minimal(self):
        d = {"resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_ENV_NAME, conf.env_name)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual([constants.DEFAULT_JOB_TYPE], conf.job_type)
        self.assertEqual(constants.DEFAULT_QUEUE, conf.queue)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.networks)

    def test_from_dictionnary_some_metadatas(self):
        d = {
            "job_name": "test",
            "queue": "production",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_ENV_NAME, conf.env_name)
        self.assertEqual("test", conf.job_name)
        self.assertEqual([constants.DEFAULT_JOB_TYPE], conf.job_type)
        self.assertEqual("production", conf.queue)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)

    def test_from_dictionnary_job_types(self):
        d = {
            "job_name": "test",
            "queue": "production",
            "job_type": "allow_classic_ssh",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(["allow_classic_ssh"], conf.job_type)

        d["job_type"] = "bla"
        with self.assertRaises(ValidationError):
            conf = Configuration.from_dictionnary(d)

        d["job_type"] = ["allow_classic_ssh"]
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(["allow_classic_ssh"], conf.job_type)

        d["job_type"] = ["allow_classic_ssh", "bla"]
        with self.assertRaises(ValidationError):
            conf = Configuration.from_dictionnary(d)

    def test_from_dictionnary_invalid_walltime(self):
        d = {"walltime": "02:00", "resources": {"machines": [], "networks": []}}
        with self.assertRaises(ValidationError):
            Configuration.from_dictionnary(d)
    
    def test_from_dictionnary_big_walltime(self):
        d = {"walltime": "200:00:00", "resources": {"machines": [], "networks": []}}
        self.assertTrue(Configuration.from_dictionnary(d))

    def test_missing_cluster_and_servers(self):
        d = {
            "resources": {
                "machines": [{"roles": ["r1"], "nodes": 1, "primary_network": "n1"}],
                "networks": [],
            }
        }
        with self.assertRaises(ValidationError):
            conf = Configuration.from_dictionnary(d)

    def test_servers_set_cluster(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 1,
                        "primary_network": "n1",
                        "servers": ["foo-1.site.grid5000.fr", "foo-2.site.grid5000.fr"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "site", "type": "prod"}
                ],
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual("foo", conf.machines[0].cluster)

    def test_servers_different_cluster(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 1,
                        "primary_network": "n1",
                        "servers": ["foo-1.site.grid5000.fr", "bar-2.site.grid5000.fr"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "site", "type": "prod"}
                ],
            }
        }
        with self.assertRaises(ValueError):
            Configuration.from_dictionnary(d)

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionnary_with_machines(self, mock_get_cluster_site):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluster1",
                        "primary_network": "n1",
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "siteA", "type": "prod"}
                ],
            }
        }

        conf = Configuration.from_dictionnary(d)
        self.assertTrue(len(conf.machines) == 1)
        self.assertTrue(len(conf.networks) == 1)

        machine_group = conf.machines[0]
        network = conf.networks[0]

        self.assertEqual(2, machine_group.nodes)

        # check the network ref
        self.assertEqual(network, machine_group.primary_network)

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionnary_with_machines_and_secondary_networks(
        self, mock_get_cluster_site
    ):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                        "primary_network": "n1",
                        "secondary_networks": ["n2"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "siteA", "type": "prod"},
                    {"id": "n2", "roles": ["rn2"], "site": "siteA", "type": "kavlan"},
                ],
            }
        }

        conf = Configuration.from_dictionnary(d)
        self.assertTrue(len(conf.machines) == 1)
        self.assertTrue(len(conf.networks) == 2)

        machine_group = conf.machines[0]
        networks = conf.networks

        self.assertEqual(2, machine_group.nodes)

        # check the network ref
        self.assertTrue(machine_group.primary_network in networks)
        self.assertEqual("n1", machine_group.primary_network.id)
        self.assertEqual(1, len(machine_group.secondary_networks))
        self.assertTrue(machine_group.secondary_networks[0] in networks)
        self.assertEqual("n2", machine_group.secondary_networks[0].id)

    def test_from_dictionnary_no_network(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                        "primary_network": "n1",
                    }
                ],
                "networks": [],
            }
        }

        with self.assertRaises(ValueError) as _:
            Configuration.from_dictionnary(d)

    def test_from_dictionnary_unbound_network(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                        "primary_network": "n1",
                    }
                ],
                "networks": [
                    {
                        "id": "unbound_network",
                        "roles": ["rn1"],
                        "site": "siteA",
                        "type": "prod",
                    }
                ],
            }
        }

        with self.assertRaises(ValueError) as _:
            Configuration.from_dictionnary(d)

    def test_from_dictionnary_no_secondary_networks(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                        "primary_network": "n1",
                        "secondary_networks": ["n2"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "siteA", "type": "prod"}
                ],
            }
        }

        with self.assertRaises(ValueError) as ctx:
            conf = Configuration.from_dictionnary(d)

    def test_from_dictionnary_unbound_secondary_networks(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                        "primary_network": "n1",
                        "secondary_networks": ["n2"],
                    }
                ],
                "networks": [
                    {"id": "network", "roles": ["n1"], "site": "siteA", "type": "prod"},
                    {
                        "id": "unbound_network",
                        "roles": ["nr2"],
                        "site": "siteA",
                        "type": "kavlan",
                    },
                ],
            }
        }

        with self.assertRaises(ValueError) as ctx:
            conf = Configuration.from_dictionnary(d)

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_programmatic(self, mock_get_cluster_site):
        conf = Configuration()
        network = NetworkConfiguration(
            id="id", roles=["my_network"], type="prod", site="rennes"
        )

        conf.add_network_conf(network).add_machine_conf(
            ClusterConfiguration(
                roles=["r1"], cluster="paravance", primary_network=network
            )
        ).add_machine_conf(
            ClusterConfiguration(
                roles=["r2"], cluster="parapluie", primary_network=network, nodes=10
            )
        )

        conf.finalize()

        self.assertEqual(2, len(conf.machines))
        self.assertEqual(1, len(conf.networks))


class TestNetworkConfiguration(EnosTest):
    def test_network_minimal(self):
        n = {"id": "n1", "roles": ["r1"], "site": "siteA", "type": "prod"}

        network = NetworkConfiguration.from_dictionnary(n)
        self.assertEqual("siteA", network.site)
        self.assertEqual(["r1"], network.roles)
        self.assertEqual("prod", network.type)
        self.assertEqual("n1", network.id)
