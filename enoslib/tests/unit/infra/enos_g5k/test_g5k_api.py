import mock
from mock import patch
import os

from enoslib.infra.enos_g5k.g5k_api_utils import _deploy
from enoslib.tests.unit import EnosTest


class TestDeploy(EnosTest):
    def test_deploy_no_undeployed(self):
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], [], 0, {})
            m.assert_not_called()

    def test_deploy_max_count(self):
        deploy = mock.Mock()
        with patch("enoslib.infra.enos_g5k.g5k_api_utils.deploy") as m:
            deployed, undeployed = _deploy("rennes", [], [], 4, {})
            m.assert_not_called()

    def test_deploy_2_deploy(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[([1], [2]), ([2], [])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], [1, 2], 0, {})
            self.assertCountEqual([1, 2], deployed)
            self.assertCountEqual([], undeployed)

    def test_deploy_3_deploy(self):
        with patch(
            "enoslib.infra.enos_g5k.g5k_api_utils.deploy",
            side_effect=[([1], [2]), ([], [2]), ([], [2])],
        ) as m:
            deployed, undeployed = _deploy("rennes", [], [1, 2], 0, {})
            self.assertCountEqual([1], deployed)
            self.assertCountEqual([2], undeployed)
