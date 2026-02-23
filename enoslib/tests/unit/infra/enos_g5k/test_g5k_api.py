from unittest.mock import MagicMock, patch

from grid5000.objects import Job

from enoslib.infra.enos_g5k.g5k_api_utils import (
    _do_grid_make_reservation,
    _evaluate_job_types_consistency,
    available_kwollect_metrics,
    grid_get_create_or_update_job,
)
from enoslib.tests.unit import EnosTest
from enoslib.tests.unit.infra.enos_g5k.utils import get_offline_client


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

    def test_dynamic_before_specific_resources(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.submit_jobs") as p:
            _do_grid_make_reservation(
                dict(city=["{'dynamic'}", "{network_address in 'specific'}"]),
                "test_name",
                "12:34:56",
                "2022-04-01 12:00:00",
                "test_queue",
                "test_job_type",
                "test_monitor",
                "test_project",
            )

            resources = "{network_address in 'specific'}+{'dynamic'},walltime=12:34:56"

            p.assert_called_once_with(
                [
                    (
                        "city",
                        dict(
                            name="test_name",
                            types=["test_job_type", "monitor=test_monitor"],
                            resources=resources,
                            queue="test_queue",
                            project="test_project",
                            command="sleep 31536000",
                            reservation="2022-04-01 12:00:00",
                        ),
                    )
                ]
            )

    def test_specific_before_dynamic_resources(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.submit_jobs") as p:
            _do_grid_make_reservation(
                dict(city=["{network_address in 'specific'}", "{'dynamic'}"]),
                "test_name",
                "12:34:56",
                "2022-04-01 12:00:00",
                "test_queue",
                "test_job_type",
                "test_monitor",
                "test_project",
            )

            resources = "{network_address in 'specific'}+{'dynamic'},walltime=12:34:56"

            p.assert_called_once_with(
                [
                    (
                        "city",
                        dict(
                            name="test_name",
                            types=["test_job_type", "monitor=test_monitor"],
                            resources=resources,
                            queue="test_queue",
                            project="test_project",
                            command="sleep 31536000",
                            reservation="2022-04-01 12:00:00",
                        ),
                    )
                ]
            )


@patch("enoslib.infra.enos_g5k.g5k_api_utils._evaluate_job_types_consistency")
@patch("enoslib.infra.enos_g5k.g5k_api_utils.grid_make_reservation")
@patch("enoslib.infra.enos_g5k.g5k_api_utils.grid_destroy_from_name")
@patch("enoslib.infra.enos_g5k.g5k_api_utils.grid_reload_jobs_from_name")
class TestGridGetCreateOrUpdateJob(EnosTest):

    def _call_target(self):
        return grid_get_create_or_update_job(
            "test_name",
            "12:34:56",
            "2022-04-01 12:00:00",
            "test_queue",
            [],
            "test_monitor",
            "test_project",
            [],
            [],
        )

    def test_no_reload(
        self,
        mock_grid_reload_jobs_from_name,
        mock_grid_destroy_from_name,
        mock_grid_make_reservation,
        mock__evaluate_job_types_consistency,
    ):
        mock_job = MagicMock()
        mock_grid_reload_jobs_from_name.return_value = []
        mock_grid_make_reservation.return_value = [mock_job]

        jobs = self._call_target()

        mock__evaluate_job_types_consistency.assert_not_called()
        mock_grid_destroy_from_name.assert_not_called()
        mock_grid_make_reservation.assert_called_once()
        self.assertEqual(jobs, [mock_job])

    def test_reload_do_not_recreate(
        self,
        mock_grid_reload_jobs_from_name,
        mock_grid_destroy_from_name,
        mock_grid_make_reservation,
        mock__evaluate_job_types_consistency,
    ):
        mock_job = MagicMock()
        mock_grid_reload_jobs_from_name.return_value = [mock_job]

        mock__evaluate_job_types_consistency.return_value = (True, set())

        jobs = self._call_target()

        mock__evaluate_job_types_consistency.assert_called_once()
        mock_grid_destroy_from_name.assert_not_called()
        mock_grid_make_reservation.assert_not_called()
        self.assertEqual(jobs, [mock_job])

    def test_reload_must_recreate(
        self,
        mock_grid_reload_jobs_from_name,
        mock_grid_destroy_from_name,
        mock_grid_make_reservation,
        mock__evaluate_job_types_consistency,
    ):
        mock_job = MagicMock()
        mock_grid_reload_jobs_from_name.return_value = [mock_job]

        mock__evaluate_job_types_consistency.return_value = (False, set())

        mock_grid_make_reservation.return_value = ["new_job"]

        jobs = self._call_target()

        mock__evaluate_job_types_consistency.assert_called_once()
        mock_grid_destroy_from_name.assert_called_once()
        mock_grid_make_reservation.assert_called_once()
        self.assertEqual(jobs, ["new_job"])


class TestEvaluateJobTypesConsistency(EnosTest):

    def _get_mocked_job(
        self, has_job_types: bool = False, has_deploy_job_type: bool = False
    ):
        job = MagicMock(spec=Job)
        list_job_types = []
        if has_job_types:
            list_job_types.extend(["sudo-g5k", "besteffort"])
        if has_deploy_job_type:
            list_job_types.append("deploy")
        job.types = list_job_types
        return job

    def test_no_reload(self):
        is_consistent, extra_job_types = _evaluate_job_types_consistency(
            jobs=[], job_type=[]
        )

        self.assertTrue(is_consistent)
        self.assertEqual(len(extra_job_types), 0)

    def test_reload_match_on_job_types_extra_types(self):

        job_1 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)
        job_2 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)

        is_consistent, extra_job_types = _evaluate_job_types_consistency(
            jobs=[job_1, job_2], job_type=["deploy"]
        )

        job_types = sorted(extra_job_types)

        self.assertTrue(is_consistent)
        self.assertEqual(job_types, ["besteffort", "sudo-g5k"])

    def test_reload_match_on_job_types_no_extra_types(self):

        job_1 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)
        job_2 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)

        is_consistent, extra_job_types = _evaluate_job_types_consistency(
            jobs=[job_1, job_2], job_type=["sudo-g5k", "besteffort", "deploy"]
        )

        self.assertTrue(is_consistent)
        self.assertEqual(len(extra_job_types), 0)

    def test_reload_no_match_on_job_types(self):

        job_1 = self._get_mocked_job(has_job_types=True)
        job_2 = self._get_mocked_job(has_job_types=True)

        is_consistent, extra_job_types = _evaluate_job_types_consistency(
            jobs=[job_1, job_2], job_type=["exotic"]
        )

        self.assertFalse(is_consistent)
        self.assertEqual(len(extra_job_types), 0)

    def test_reload_unwanted_deploy(self):

        job_1 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)
        job_2 = self._get_mocked_job(has_job_types=True, has_deploy_job_type=True)

        is_consistent, extra_job_types = _evaluate_job_types_consistency(
            jobs=[job_1, job_2], job_type=["sudo-g5k", "besteffort"]
        )

        self.assertFalse(is_consistent)
        self.assertEqual(len(extra_job_types), 0)


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
