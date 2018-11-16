from enoslib.infra.enos_vmong5k.configuration import Configuration, MachineConfiguration
import enoslib.infra.enos_vmong5k.constants as constants

from ... import EnosTest

import jsonschema


class TestConfiguration(EnosTest):

    def test_from_dictionnary_minimal(self):
        d = {
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.machines)

    def test_from_dictionnary_custom_backend(self):
        d = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {
                "machines": [],
                "networks": []
            }
        }
        conf = Configuration.from_dictionnary(d)
        self.assertEqual("test-job", conf.job_name)
        self.assertEqual("12:34:56", conf.walltime)

    def test_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration(roles=["r1"],
                                                   flavour=constants.FLAVOURS["large"],
                                                   number=10,
                                                   cluster="test-cluster"
                                                   ))
        conf.finalize()
        self.assertEqual(1, len(conf.machines))
        # default networks
        self.assertEqual(constants.DEFAULT_NETWORKS, conf.networks)

    def test_programmatic_missing_keys(self):
        conf = Configuration()
        conf.add_machine_conf(MachineConfiguration())
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()


class TestMachineConfiguration(EnosTest):

    def test_from_dictionnary_minimal(self):
        d = {
            "roles": ["r1"],
            "cluster": "test-cluster"
        }
        conf = MachineConfiguration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_FLAVOUR, conf.flavour)

    def test_from_dictionnary(self):
        d = {
            "roles": ["r1"],
            "flavour": "large",
            "number": 2,
            "cluster": "test-cluster"
        }
        conf = MachineConfiguration.from_dictionnary(d)
        self.assertEqual(constants.FLAVOURS["large"], conf.flavour)
        self.assertEqual(2, conf.number)
