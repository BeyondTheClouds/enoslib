from enoslib.utils import get_roles_as_list
from enoslib.tests.unit import EnosTest

class TestGetRolesAsList(EnosTest):

        def test_role(self):
            desc = {
                "role": "r1"
            }

            self.assertCountEqual(["r1"], get_roles_as_list(desc))


        def test_roles(self):
            desc = {
                "roles": ["r1", "r2"]
            }

            self.assertCountEqual(["r1", "r2"], get_roles_as_list(desc))

        def test_role_and_roles(self):
            desc = {
                "role": "r1",
                "roles": ["r2", "r3"]
            }
            self.assertCountEqual(["r2", "r3"], get_roles_as_list(desc))
