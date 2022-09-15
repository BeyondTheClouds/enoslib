from enoslib.infra.enos_static.provider import Static
from enoslib.infra.enos_static.configuration import Configuration
from enoslib.tests.unit import EnosTest


class TestBuildResources(EnosTest):
    def test_build_resources(self):

        resources = {
            "machines": [
                {"address": "ip1", "roles": ["role1", "role2"]},
                {"address": "ip2", "roles": ["role1"]},
            ],
            "networks": [
                {
                    "cidr": "2.2.3.1/24",
                    "roles": ["net2"],
                    "gateway": "2.2.3.254",
                    "dns": "2.2.3.253",
                },
                {
                    "cidr": "1.2.3.4/24",
                    "roles": ["net1"],
                    "start": "1.2.3.100",
                    "end": "1.2.3.252",
                    "gateway": "1.2.3.254",
                    "dns": "1.2.3.253",
                },
            ],
        }
        conf = Configuration.from_dictionary({"resources": resources})
        s = Static(conf)
        roles, networks = s.init()
        self.assertCountEqual(["role1", "role2"], roles.keys())
        self.assertEqual(2, len(roles["role1"]))
        self.assertEqual(1, len(roles["role2"]))
        self.assertEqual(2, len(networks))
        self.assertTrue(
            str(networks["net1"][0].network) in ["1.2.3.0/24", "2.2.3.0/24"]
        )
