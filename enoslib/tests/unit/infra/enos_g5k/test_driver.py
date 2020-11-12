import mock
import unittest

from enoslib.infra.enos_g5k.driver import *


class TestGetDriver(unittest.TestCase):
    def test_getdriver_oargriddynamic(self):
        gk = mock.Mock()
        driver = get_driver(Configuration())
        self.assertIsInstance(driver, OargridDynamicDriver)

    def test_getdriver_oargridstatic(self):
        resources = {
            "oargrid_jobids": ["rennes", "1234"],
            "resources": {"machines": [], "networks": []},
        }
        c = Configuration.from_settings(oargrid_jobids=["rennes", "1234"])
        gk = mock.Mock()
        driver = get_driver(c)
        self.assertIsInstance(driver, OargridStaticDriver)
