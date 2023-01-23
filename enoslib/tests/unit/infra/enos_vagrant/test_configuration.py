from typing import Dict

import jsonschema
from jsonschema.exceptions import ValidationError

import enoslib.infra.enos_vagrant.constants as constants
from enoslib.infra.enos_vagrant.configuration import (
    Configuration,
    MachineConfiguration,
    NetworkConfiguration,
)
from enoslib.infra.enos_vagrant.constants import FLAVOURS

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d: Dict = {"resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_BACKEND, conf.backend)
        self.assertEqual(constants.DEFAULT_BOX, conf.box)
        self.assertEqual(constants.DEFAULT_USER, conf.user)

    def test_from_dictionary_custom_backend(self):
        d: Dict = {
            "backend": "virtualbox",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("virtualbox", conf.backend)

    def test_missing_flavour_and_flavour_desc(self):
        d: Dict = {
            "backend": "virtualbox",
            "resources": {"machines": [{"roles": ["role1"]}], "networks": []},
        }
        with self.assertRaises(ValidationError):
            _ = Configuration.from_dictionary(d)

    def test_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"], flavour_desc=FLAVOURS["large"], number=10
            )
        ).add_network_conf(NetworkConfiguration(roles=["net1"], cidr="192.168.2.1/24"))

        conf.finalize()
        self.assertEqual(1, len(conf.machines))

    def test_programmatic_missing_keys(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration())
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()


class TestMachineConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d: Dict = {"roles": ["r1"]}
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_FLAVOUR[1], conf.flavour_desc)
        self.assertEqual(constants.DEFAULT_NUMBER, conf.number)

    def test_from_dictionary(self):
        d: Dict = {"roles": ["r1"], "flavour": "large", "number": 2}
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.FLAVOURS["large"], conf.flavour_desc)
        self.assertEqual(2, conf.number)

    def test_from_dictionary_flavour_desc(self):
        flavour_desc = {"core": 43, "mem": 42}
        d: Dict = {"roles": ["r1"], "flavour_desc": flavour_desc, "number": 2}
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(flavour_desc, conf.flavour_desc)
        self.assertEqual(2, conf.number)
