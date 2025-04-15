import enoslib.infra.enos_chameleonkvm.constants as constants
from enoslib.infra.enos_chameleonkvm.configuration import (
    Configuration,
    MachineConfiguration,
)

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

    def test_only_global_image(self):
        image = "CC-Ubuntu22.04"
        d = {
            "walltime": "01:00:00",
            "lease_name": "lease-name",
            "rc_file": "rc_file",
            "key_name": "key-name",
            "image": image,
            "resources": {
                "machines": [
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                    }
                ],
                "networks": ["sharednet1"],
            },
        }
        conf = Configuration.from_dictionary(d)

        self.assertEqual(image, conf.image)
        self.assertEqual(image, conf.machines[0].image)

    def test_no_global__no_local_image(self):
        d = {
            "walltime": "01:00:00",
            "lease_name": "lease-name",
            "rc_file": "rc_file",
            "key_name": "key-name",
            "resources": {
                "machines": [
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                    }
                ],
                "networks": ["sharednet1"],
            },
        }
        conf = Configuration.from_dictionary(d)
        conf.finalize()

        self.assertEqual(constants.DEFAULT_IMAGE, conf.image)
        self.assertEqual(constants.DEFAULT_IMAGE, conf.machines[0].image)

    def test_no_global_different_local_images(self):
        image = "CC-Ubuntu22.04"
        d = {
            "walltime": "01:00:00",
            "lease_name": "lease-name",
            "rc_file": "rc_file",
            "key_name": "key-name",
            "resources": {
                "machines": [
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                        "image": image,
                    },
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                        "image": image.replace("22", "24"),
                    },
                ],
                "networks": ["sharednet1"],
            },
        }
        conf = Configuration.from_dictionary(d)
        conf.finalize()

        self.assertEqual(constants.DEFAULT_IMAGE, conf.image)
        self.assertEqual(image, conf.machines[0].image)
        self.assertEqual(image.replace("22", "24"), conf.machines[1].image)

    def test_global_image(self):
        image = "CC-Ubuntu22.04"
        d = {
            "walltime": "01:00:00",
            "lease_name": "lease-name",
            "rc_file": "rc_file",
            "key_name": "key-name",
            "image": image.replace("22", "24"),
            "resources": {
                "machines": [
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                        "image": image,
                    },
                    {
                        "roles": ["worker"],
                        "flavour": "compute_zen3",
                        "number": 1,
                    },
                ],
                "networks": ["sharednet1"],
            },
        }
        conf = Configuration.from_dictionary(d)
        conf.finalize()

        self.assertEqual(image.replace("22", "24"), conf.image)
        self.assertEqual(image, conf.machines[0].image)
        self.assertEqual(image.replace("22", "24"), conf.machines[1].image)
