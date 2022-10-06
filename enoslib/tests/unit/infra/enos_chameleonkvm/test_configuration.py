from enoslib.infra.enos_chameleonkvm.configuration import (
    Configuration,
    MachineConfiguration,
)
import enoslib.infra.enos_chameleonkvm.constants as constants

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {"key_name": "test-key", "resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_IMAGE, conf.image)
        self.assertEqual(constants.DEFAULT_USER, conf.user)
        self.assertEqual(constants.DEFAULT_NAMESERVERS, conf.dns_nameservers)

    def test_from_settings(self):
        conf = Configuration.from_settings(key_name="test-key", image="image")
        self.assertEqual("image", conf.image)
        self.assertEqual(constants.DEFAULT_USER, conf.user)
        self.assertEqual(constants.DEFAULT_NAMESERVERS, conf.dns_nameservers)

    def test_programmatic_con(self):
        conf = Configuration.from_settings(key_name="test-key")
        conf.add_machine_conf(
            MachineConfiguration(roles=["test-role"], flavour="m1.tiny", number=1)
        )
        conf.add_network_conf("api_network")
        conf.finalize()
        self.assertEqual(1, len(conf.machines))
        self.assertEqual(1, len(conf.networks))

    def test_programmatic(self):
        conf = Configuration.from_settings(key_name="test-key")
        conf.add_machine(roles=["test-role"], flavour="m1.tiny", number=1).add_network(
            "api_network"
        )

        conf.finalize()
        self.assertEqual(1, len(conf.machines))
        self.assertEqual(1, len(conf.networks))
