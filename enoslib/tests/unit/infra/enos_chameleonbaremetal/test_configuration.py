from enoslib.infra.enos_chameleonbaremetal.configuration import Configuration, MachineConfiguration
import enoslib.infra.enos_chameleonbaremetal.constants as constants

from ... import EnosTest


class TestConfiguration(EnosTest):

    def test_from_dictionnary_minimal(self):
        d = {
            "key_name": "test-key",
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_IMAGE, conf.image)
        self.assertEqual(constants.DEFAULT_USER, conf.user)
        self.assertEqual(constants.DEFAULT_NAMESERVERS, conf.dns_nameservers)


    def test_programmatic_conf(self):
        conf = Configuration.from_settings(key_name="test-key")
        conf.add_machine_conf(MachineConfiguration(roles=["test-role"],
                                                   flavour="m1.tiny",
                                                   number=1))
        conf.add_network("api_network")
        conf.finalize()

        self.assertEqual(1, len(conf.machines))
        self.assertEqual(1, len(conf.networks))

    def test_programmatic(self):
        conf = Configuration.from_settings(key_name="test-key")
        conf.add_machine(roles=["test-role"],
                         flavour="m1.tiny",
                         number=1)\
            .add_network("api_network")

        conf.finalize()
        self.assertEqual(1, len(conf.machines))
        self.assertEqual(1, len(conf.networks))

