from enoslib.infra.enos_static.provider import Static
from enoslib.tests.unit import EnosTest

class TestBuildResources(EnosTest):

    def test_build_resources(self):

        resources = {
            "machines":[{
                "address": "ip1",
                "roles": ["role1", "role2"]
            },{
                "address": "ip2",
                "role": "role1"
            }],
            "networks": [{
                "cidr": "cidr1",
                "roles": ["net1", "net2"]
            },{
                "cidr": "cidr2",
                "role": "net1"
            }]
        }

        s = Static({"resources": resources})
        roles, _ = s.init()
        self.assertCountEqual(["role1", "role2"], roles.keys())
        self.assertEquals(2, len(roles["role1"]))
        self.assertEquals(1, len(roles["role2"]))
