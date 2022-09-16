import jsonschema

from enoslib.infra.enos_vmong5k.configuration import Configuration, MachineConfiguration
import enoslib.infra.enos_vmong5k.constants as constants
from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {"resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.machines)

    def test_from_dictionary_custom_backend(self):
        d = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {"machines": [], "networks": []},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("test-job", conf.job_name)
        self.assertEqual("12:34:56", conf.walltime)

    def test_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"], flavour="large", number=10, cluster="test-cluster"
            )
        )
        conf.finalize()
        self.assertEqual(1, len(conf.machines))
        # default networks
        self.assertEqual(constants.DEFAULT_NETWORKS, conf.networks)

    def test_programmatic_missing_keys(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration())
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()

    def test_wrong_mac_detected(self):
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"],
                flavour="large",
                number=10,
                cluster="test-cluster",
                macs=["gg"],
            )
        )
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()


class TestMachineConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {"roles": ["r1"], "cluster": "test-cluster"}
        conf = MachineConfiguration.from_dictionary(d)
        flavour, flavour_desc = constants.DEFAULT_FLAVOUR
        self.assertEqual(flavour, conf.flavour)
        self.assertEqual(flavour_desc, conf.flavour_desc)

    def test_from_dictionary(self):
        d = {
            "roles": ["r1"],
            "flavour": "large",
            "number": 2,
            "cluster": "test-cluster",
        }
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.FLAVOURS["large"], conf.flavour_desc)
        self.assertEqual(2, conf.number)

    def test_from_dictionary_flavour_desc(self):
        flavour_desc = {"core": 42, "mem": 42}
        d = {
            "roles": ["r1"],
            "flavour_desc": flavour_desc,
            "number": 2,
            "cluster": "test-cluster",
        }
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(flavour_desc, conf.flavour_desc)
        self.assertEqual(2, conf.number)
