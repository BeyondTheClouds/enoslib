from unittest.mock import patch


from enoslib.infra.enos_g5k.g5k_api_utils import _deploy, _do_grid_make_reservation
from enoslib.tests.unit import EnosTest


class TestDeploy(EnosTest):
    def test_deploy_no_undeployed(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], [], 0, {})
            m.assert_not_called()

    def test_deploy_max_count(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], [], 4, {})
            m.assert_not_called()

    def test_deploy_2_deploy(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[([1], [2]), ([2], [])],
        ) as _:
            deployed, undeployed = _deploy("rennes", [], [1, 2], 0, {})
            self.assertCountEqual([1, 2], deployed)
            self.assertCountEqual([], undeployed)

    def test_deploy_3_deploy(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[([1], [2]), ([], [2]), ([], [2])],
        ) as _:
            deployed, undeployed = _deploy("rennes", [], [1, 2], 0, {})
            self.assertCountEqual([1], deployed)
            self.assertCountEqual([2], undeployed)


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
