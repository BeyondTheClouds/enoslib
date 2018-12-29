import jsonschema

from enoslib.infra.enos_static.configuration import Configuration, NetworkConfiguration, MachineConfiguration
from ... import EnosTest



class TestConfiguration(EnosTest):

    def test_from_dictionnary_minimal(self):
        d = {
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.networks)

    def test_programmatic_missing_keys(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration())
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()

    def test_programmatic_missing_address(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration(roles=["plop"]))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()

    def test_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration(roles=["role"],
                                                   address="1.2.3.4"))
        conf.add_network_conf(NetworkConfiguration(roles=["nrole"],
                                                   start="1.2.3.10",
                                                   end="1.2.3.15",
                                                   cidr="1.2.3.4/24",
                                                   gateway="1.2.3.254",
                                                   dns="1.2.3.253"))
        conf.finalize()
        self.assertEqual(1, len(conf.machines))
