""" test the check() function"""

import logging
from typing import List, Optional, Tuple

import enoslib as en
from enoslib.tests.unit import EnosTest


class TestCheck(EnosTest):
    """test the check() function"""

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.global_deps: List[Tuple[str, Optional[bool], str, str]] = []
        en._print_conn_table = self._fake_print_conn_table

    def _fake_print_conn_table(self, deps, _console):
        """fake print_conn_table"""
        self.global_deps = deps

    def test_normal_check(self):
        """basic check"""
        en.init_logging(level=logging.INFO)
        en.check()
        normal_deps = en._check_deps()  # [protected-access]
        self.assertTrue(len(normal_deps) == len(self.global_deps))

    def test_check(self):
        """check only one platform"""
        en.init_logging(level=logging.INFO)
        en.check(["Grid'5000"])
        normal_deps = en._check_deps()  # [protected-access]
        self.assertTrue(len(self.global_deps) == 1)
        self.assertTrue(len(normal_deps) > 0)

    def test_check_wrong(self):
        """check only one platform but it does not exist"""
        en.init_logging(level=logging.WARNING)
        en.check(["NO_EXISTING"])
        normal_deps = en._check_deps()  # [protected-access]
        self.assertTrue(len(self.global_deps) == 0)
        self.assertTrue(len(normal_deps) > 0)
