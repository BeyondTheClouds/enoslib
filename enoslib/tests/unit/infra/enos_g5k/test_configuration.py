import warnings

from jsonschema.exceptions import ValidationError
import pytest
from unittest.mock import patch

from enoslib.infra.enos_g5k.configuration import (
    ClusterConfiguration,
    Configuration,
    NetworkConfiguration,
    ServersConfiguration,
)
import enoslib.infra.enos_g5k.constants as constants

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {"resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual([], conf.job_type)
        self.assertEqual(constants.DEFAULT_QUEUE, conf.queue)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.networks)

    def test_from_dictionary_some_metadatas(self):
        d = {
            "job_name": "test",
            "queue": "production",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("test", conf.job_name)
        self.assertEqual([], conf.job_type)
        self.assertEqual("production", conf.queue)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)

    def test_from_dictionary_job_types(self):
        d = {
            "job_name": "test",
            "queue": "production",
            "job_type": "exotic",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(["exotic"], conf.job_type)

        d["job_type"] = "bla"
        with self.assertRaises(ValidationError):
            conf = Configuration.from_dictionary(d)

        d["job_type"] = ["exotic"]
        conf = Configuration.from_dictionary(d)
        self.assertEqual(["exotic"], conf.job_type)

        d["job_type"] = ["exotic", "bla"]
        with self.assertRaises(ValidationError):
            conf = Configuration.from_dictionary(d)

    def test_from_dictionary_deploy_job(self):
        d = {
            "job_name": "test",
            "queue": "production",
            "job_type": ["deploy"],
            "env_name": "debian11-nfs",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(["deploy"], conf.job_type)
        self.assertEqual("debian11-nfs", conf.env_name)

        d["job_type"] = []
        # Needs deploy job type, but still accepted for compatibility
        with pytest.deprecated_call():
            conf = Configuration.from_dictionary(d)

        d["job_type"] = ["deploy"]
        del d["env_name"]
        # Needs env_name
        with self.assertRaises(ValueError):
            conf = Configuration.from_dictionary(d)

        d["job_type"] = []
        conf = Configuration.from_dictionary(d)
        self.assertEqual([], conf.job_type)

    def test_from_dictionary_invalid_walltime(self):
        d = {"walltime": "02:00", "resources": {"machines": [], "networks": []}}
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_big_walltime(self):
        d = {"walltime": "200:00:00", "resources": {"machines": [], "networks": []}}
        self.assertTrue(Configuration.from_dictionary(d))

    def test_missing_cluster_and_servers(self):
        d = {
            "resources": {
                "machines": [{"roles": ["r1"], "nodes": 1, "primary_network": "n1"}],
                "networks": [],
            }
        }
        with self.assertRaises(ValidationError):
            _ = Configuration.from_dictionary(d)

    def test_from_dictionary_invalid_hostname(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "primary_network": "n1",
                        "servers": ["foo-1"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "site", "type": "prod"}
                ],
            }
        }

        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_servers_same_cluster(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "primary_network": "n1",
                        "servers": ["foo-1.site.grid5000.fr", "foo-2.site.grid5000.fr"],
                    }
                ],
                "networks": [
                    {"id": "n1", "roles": ["rn1"], "site": "site", "type": "prod"}
                ],
            }
        }
        conf = Configuration.from_dictionary(d)
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
            Configuration.from_dictionary(d)

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionary_with_machines(self, mock_get_cluster_site):
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

        conf = Configuration.from_dictionary(d)
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
    def test_from_dictionary_with_machines_and_secondary_networks(
        self, mock_get_cluster_site
    ):
        d = {
            "job_type": ["deploy"],
            "env_name": "debian11-min",
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
            },
        }

        conf = Configuration.from_dictionary(d)
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

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionary_with_warnings_kavlan(self, mock_get_cluster_site):
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

        # Missing env_name and deploy job type
        with pytest.deprecated_call():
            _ = Configuration.from_dictionary(d)

        d["job_type"] = ["deploy"]
        # Missing env_name
        with pytest.deprecated_call():
            _ = Configuration.from_dictionary(d)

        del d["job_type"]
        d["env_name"] = "debian11-min"
        # Missing deploy job_type
        with pytest.deprecated_call():
            _ = Configuration.from_dictionary(d)

        d["job_type"] = ["deploy"]
        d["env_name"] = "debian11-min"
        # Should not emit any deprecation warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _ = Configuration.from_dictionary(d)

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionary_default_network(self, mock_get_cluster_site):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                    }
                ],
                "networks": [],
            }
        }

        conf = Configuration.from_dictionary(d)
        self.assertTrue(len(conf.machines) == 1)
        self.assertTrue(len(conf.networks) == 1)

        machine_group = conf.machines[0]
        network = conf.networks[0]

        # check the network ref
        self.assertTrue(machine_group.primary_network in conf.networks)
        self.assertEqual(network.id, machine_group.primary_network.id)
        # check site
        self.assertEqual(network.site, "siteA")

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_from_dictionary_no_network(self, mock_get_cluster_site):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "nodes": 2,
                        "cluster": "cluste1",
                    }
                ],
            }
        }

        conf = Configuration.from_dictionary(d)
        self.assertTrue(len(conf.machines) == 1)
        self.assertTrue(len(conf.networks) == 1)

        machine_group = conf.machines[0]
        network = conf.networks[0]

        # check the network ref
        self.assertTrue(machine_group.primary_network in conf.networks)
        self.assertEqual(network.id, machine_group.primary_network.id)
        # check site
        self.assertEqual(network.site, "siteA")

    def test_from_dictionary_unknown_network(self):
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
            Configuration.from_dictionary(d)

    def test_from_dictionary_unbound_network(self):
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
            Configuration.from_dictionary(d)

    def test_from_dictionary_no_secondary_networks(self):
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

        with self.assertRaises(ValueError) as _:
            Configuration.from_dictionary(d)

    def test_from_dictionary_unbound_secondary_networks(self):
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

        with self.assertRaises(ValueError) as _:
            Configuration.from_dictionary(d)

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

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_programmatic_invalid(self, mock_get_cluster_site):
        conf = Configuration.from_settings(walltime="02:00")
        with self.assertRaises(ValidationError) as cm:
            conf.finalize()
        self.assertTrue("walltime" in cm.exception.message)

        network = NetworkConfiguration(
            id="id", roles=["my_network"], type="prod", site="rennes"
        )
        conf = (
            Configuration.from_settings()
            .add_machine_conf(
                ServersConfiguration(
                    roles=["r2"], servers=["paragrid5000.fr"], primary_network=network
                )
            )
            .add_network_conf(network)
        )
        with self.assertRaises(ValidationError):
            # the error is on the hostname format
            # but for some reason this triggers a validation error on the
            # cluster vs server conf (which is true but not accurate)
            conf.finalize()

    @patch(
        "enoslib.infra.enos_g5k.configuration.get_cluster_site", return_value="siteA"
    )
    def test_programmatic_job_type(self, mock_get_cluster_site):
        conf = Configuration.from_settings(job_type=["deploy"], env_name="debian11-nfs")
        conf.finalize()

        conf = Configuration.from_settings(job_type=["deploy"])
        # Needs env_name
        with self.assertRaises(ValueError):
            conf.finalize()

        conf = Configuration.from_settings(env_name="debian11-nfs")
        # Needs deploy job type, but still accepted for compatibility
        with pytest.deprecated_call():
            conf.finalize()

        conf = Configuration.from_settings()
        conf.finalize()
        self.assertEqual([], conf.job_type)

    def test_configuration_with_reservation(self):
        conf = Configuration.from_settings(reservation="2022-06-09 16:22:00")
        conf.finalize()

    def test_configuration_with_reservation_raise_because_incoherent_time(self):
        conf = Configuration.from_settings(reservation="2022-06-09 16:61:00")
        with self.assertRaises(ValidationError):
            conf.finalize()

    def test_configuration_raise_because_of_int(self):
        conf = Configuration.from_settings(reservation=12345)
        with self.assertRaises(ValidationError):
            conf.finalize()

    def test_configuration_raise_because_of_invalid_reservation_format(self):
        conf = Configuration.from_settings(reservation="12345")
        with self.assertRaises(ValidationError):
            conf.finalize()


class TestNetworkConfiguration(EnosTest):
    def test_network_minimal(self):
        n = {"id": "n1", "roles": ["r1"], "site": "siteA", "type": "prod"}

        network = NetworkConfiguration.from_dictionary(n)
        self.assertEqual("siteA", network.site)
        self.assertEqual(["r1"], network.roles)
        self.assertEqual("prod", network.type)
        self.assertEqual("n1", network.id)
