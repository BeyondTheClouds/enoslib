from unittest.mock import patch

from enoslib.infra.enos_g5k.g5k_api_utils import (
    _deploy,
    _do_grid_make_reservation,
    available_kwollect_metrics,
)
from enoslib.tests.unit import EnosTest
from enoslib.tests.unit.infra.enos_g5k.utils import get_offline_client


class TestDeploy(EnosTest):
    def test_deploy_default_count(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[(["a"], [])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], ["a"], 1, {})
            m.assert_called_once()

    def test_deploy_max_count(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[(["a"], [])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], ["a"], 3, {})
            m.assert_called_once()

    def test_deploy_no_undeployed(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], [], 1, {})
            m.assert_not_called()

    def test_deploy_above_count(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], ["a"], 4, {})
            m.assert_not_called()

    def test_deploy_2_deploy_successful(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[(["a"], ["b"]), (["b"], [])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], ["a", "b"], 1, {})
            m.assert_called()
            self.assertCountEqual(["a", "b"], deployed)
            self.assertCountEqual([], undeployed)

    def test_deploy_3_deploy_successful(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[(["a"], ["b"]), ([], ["b"]), (["b"], [])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], ["a", "b"], 1, {})
            m.assert_called()
            self.assertCountEqual(["a", "b"], deployed)
            self.assertCountEqual([], undeployed)

    def test_deploy_3_deploy_unsuccessful(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[(["a"], ["b"]), ([], ["b"]), ([], ["b"])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], ["a", "b"], 1, {})
            m.assert_called()
            self.assertCountEqual(["a"], deployed)
            self.assertCountEqual(["b"], undeployed)


class TestDoGridMakeReservation(EnosTest):
    def test_job_spec_with_monitor(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.submit_jobs") as p:
            _do_grid_make_reservation(
                dict(rennes=["resource_spec"]),
                "test_name",
                "12:34:56",
                "2022-04-01 12:00:00",
                "test_queue",
                "test_job_type",
                "test_monitor",
                "test_project",
            )
            p.assert_called_once_with(
                [
                    (
                        "rennes",
                        dict(
                            name="test_name",
                            types=["test_job_type", "monitor=test_monitor"],
                            resources="resource_spec,walltime=12:34:56",
                            queue="test_queue",
                            project="test_project",
                            command="sleep 31536000",
                            reservation="2022-04-01 12:00:00",
                        ),
                    )
                ]
            )

    def test_job_spec_with_none(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.submit_jobs") as p:
            _do_grid_make_reservation(
                dict(rennes=["resource_spec"]),
                "test_name",
                "12:34:56",
                None,
                "test_queue",
                "test_job_type",
                None,
                None,
            )
            p.assert_called_once_with(
                [
                    (
                        "rennes",
                        dict(
                            name="test_name",
                            types=["test_job_type"],
                            resources="resource_spec,walltime=12:34:56",
                            queue="test_queue",
                            command="sleep 31536000",
                        ),
                    )
                ]
            )


class TestKwollect(EnosTest):
    @patch("enoslib.infra.enos_g5k.g5k_api_utils.get_api_client")
    def test_available_kwollect_metrics(self, mock_api):
        mock_api.return_value = get_offline_client()

        # Basic check
        res = available_kwollect_metrics(["ecotype-4.nantes.grid5000.fr"])
        self.assertIn("ecotype-4.nantes.grid5000.fr", res)
        self.assertEqual(len(res), 1)

        # Check multi-cluster on different sites
        res = available_kwollect_metrics(
            ["ecotype-12.nantes.grid5000.fr", "dahu-5.grenoble.grid5000.fr"]
        )
        self.assertIn("ecotype-12.nantes.grid5000.fr", res)
        self.assertIn("dahu-5.grenoble.grid5000.fr", res)
        self.assertEqual(len(res), 2)

        # Check "only_for" support
        gros1_wattmetre = "gros-46.nancy.grid5000.fr"
        gros2_wattmetre = "gros-66.nancy.grid5000.fr"
        gros3_nowattmetre = "gros-15.nancy.grid5000.fr"
        gros4_nowattmetre = "gros-90.nancy.grid5000.fr"
        nodes = [gros1_wattmetre, gros3_nowattmetre, gros2_wattmetre, gros4_nowattmetre]
        res = available_kwollect_metrics(nodes)
        # All nodes should have BMC metrics
        for node in nodes:
            bmc_metric = [
                metric
                for metric in res[node]
                if metric["name"] == "bmc_node_power_watt"
            ]
            self.assertEqual(len(bmc_metric), 1)
        # Only two nodes have wattmetre metrics
        for node in [gros1_wattmetre, gros2_wattmetre]:
            wattmetre_metric = [
                metric
                for metric in res[node]
                if metric["name"] == "wattmetre_power_watt"
            ]
            self.assertEqual(len(wattmetre_metric), 1)
        # Disabled for now, we have an outdated dump of the ref-api
        # for node in [gros3_nowattmetre, gros4_nowattmetre]:
        #    wattmetre_metric = [
        #        metric
        #        for metric in res[node]
        #        if metric["name"] == "wattmetre_power_watt"
        #    ]
        #    self.assertEqual(len(wattmetre_metric), 0)

        # Check support for prometheus node-exporter metrics
        node = "ecotype-4.nantes.grid5000.fr"
        res = available_kwollect_metrics([node])
        prom_metric = [
            metric
            for metric in res[node]
            if metric["name"] == "prom_node_procs_running"
        ]
        self.assertEqual(len(prom_metric), 1)

        # Check support for GPU metrics when available
        node = "sirius-1.lyon.grid5000.fr"
        res = available_kwollect_metrics([node])
        gpu_metric = [
            metric
            for metric in res[node]
            if metric["name"] == "prom_DCGM_FI_DEV_POWER_USAGE"
        ]
        self.assertEqual(len(gpu_metric), 1)
