import unittest
from enoslib.infra.enos_g5k.driver import *

class TestGetDriver(unittest.TestCase):

    def test_getdriver_oargriddynamic(self):
        resources = {
            "resources": {
                "machines": [],
                "networks": [],
            }
        }
        driver = get_driver(resources)
        self.assertIsInstance(driver, OargridDynamicDriver)

    def test_getdriver_oargridstatic(self):
        resources = {
            "oargrid_jobid": "1234",
            "resources": {
                "machines": [],
                "networks": [],
            }
        }
        driver = get_driver(resources)
        self.assertIsInstance(driver, OargridStaticDriver)

