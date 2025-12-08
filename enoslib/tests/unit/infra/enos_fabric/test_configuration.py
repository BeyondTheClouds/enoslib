import jsonschema

import enoslib.infra.enos_fabric.constants as constants
from enoslib.infra.enos_fabric.configuration import (
    Configuration,
    Fabnetv4NetworkConfiguration,
    MachineConfiguration,
)
from enoslib.infra.enos_fabric.constants import FLAVOURS

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self) -> None:
        d: dict = {
            "rc_file": "rc_file",
            "resources": {
                "machines": [],
                "networks": [{"roles": ["net1"], "kind": "FABNetv4", "site": "UCSD"}],
            },
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)
        self.assertEqual(constants.DEFAULT_SITE, conf.site)
        self.assertEqual(constants.DEFAULT_IMAGE, conf.image)
        self.assertEqual(constants.DEFAULT_USER, conf.user)

    def test_programmatic(self) -> None:
        conf = Configuration()
        conf.rc_file = "rc_file"
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"], flavour_desc=FLAVOURS["large"], number=10
            )
        ).add_network_conf(Fabnetv4NetworkConfiguration(roles=["net1"], site="UCSD"))

        conf.finalize()
        self.assertEqual(1, len(conf.machines))

    def test_programmatic_missing_keys(self) -> None:
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration())
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()


class TestMachineConfiguration(EnosTest):
    def test_from_dictionary_minimal(self) -> None:
        d: dict = {
            "roles": ["r1"],
        }
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_FLAVOUR[1], conf.flavour_desc)
        self.assertEqual(constants.DEFAULT_NUMBER, conf.number)

    def test_from_dictionary(self) -> None:
        d: dict = {"roles": ["r1"], "flavour": "large", "number": 2}
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.FLAVOURS["large"], conf.flavour_desc)
        self.assertEqual(2, conf.number)

    def test_from_dictionary_flavour_desc(self) -> None:
        flavour_desc = {"core": 43, "mem": 42}
        d: dict = {"roles": ["r1"], "flavour_desc": flavour_desc, "number": 2}
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(flavour_desc, conf.flavour_desc)
        self.assertEqual(2, conf.number)
