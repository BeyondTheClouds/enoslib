from unittest import mock
import unittest

from enoslib.infra.enos_g5k.driver import (
    OargridDynamicDriver,
    OargridStaticDriver,
    get_driver,
)

from enoslib.infra.enos_g5k.configuration import Configuration


class TestGetDriver(unittest.TestCase):
    def test_getdriver_oargriddynamic(self):
        driver = get_driver(Configuration())
        self.assertIsInstance(driver, OargridDynamicDriver)

    def test_getdriver_oargridstatic(self):
        c = Configuration.from_settings(oargrid_jobids=["rennes", "1234"])
        driver = get_driver(c)
        self.assertIsInstance(driver, OargridStaticDriver)


class TestDriverPassConf(unittest.TestCase):
    def test_driver_must_pass_info(self):
        c = Configuration.from_settings(
            job_name="TEST",
            walltime="12:34:56",
            reservation="2022-04-01 23:00:00",
            job_type=["deploy", "exotic"],
            env_name="dummy",
            monitor="test.*",
            project="project_test",
        )
        driver = get_driver(c)
        self.assertIsInstance(driver, OargridDynamicDriver)
        with mock.patch(
            "enoslib.infra.enos_g5k.driver.grid_get_or_create_job", return_value=None
        ) as p:
            driver.reserve()
            p.assert_called_with(
                "TEST",
                "12:34:56",
                "2022-04-01 23:00:00",
                "default",
                ["deploy", "exotic"],
                "test.*",
                "project_test",
                [],
                [],
                restrict_to=[],
            )
