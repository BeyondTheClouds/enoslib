from typing import Dict

import jsonschema

import enoslib.infra.enos_vmong5k.constants as constants
from enoslib.infra.enos_vmong5k.configuration import Configuration, MachineConfiguration

from ... import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d: Dict = {"resources": {"machines": [], "networks": []}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual([], conf.machines)
        self.assertEqual([], conf.networks)

    def test_from_dictionary_custom_backend(self):
        d: Dict = {
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
        d: Dict = {"roles": ["r1"], "cluster": "test-cluster"}
        conf = MachineConfiguration.from_dictionary(d)
        flavour, flavour_desc = constants.DEFAULT_FLAVOUR
        self.assertEqual(flavour, conf.flavour)
        self.assertEqual(flavour_desc, conf.flavour_desc)

    def test_from_dictionary(self):
        d: Dict = {
            "roles": ["r1"],
            "flavour": "large",
            "number": 2,
            "cluster": "test-cluster",
        }
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(constants.FLAVOURS["large"], conf.flavour_desc)
        self.assertEqual(2, conf.number)

    def test_from_dictionary_flavour_desc(self):
        flavour_desc: Dict = {"core": 42, "mem": 42}
        d: Dict = {
            "roles": ["r1"],
            "flavour_desc": flavour_desc,
            "number": 2,
            "cluster": "test-cluster",
        }
        conf = MachineConfiguration.from_dictionary(d)
        self.assertEqual(flavour_desc, conf.flavour_desc)
        self.assertEqual(2, conf.number)

    def test_vcore_type_wrong_vcore(self):
        # first from dict validates internally
        m: Dict = {"roles": ["r1"], "cluster": "test-cluster", "vcore_type": "corez"}
        d: Dict = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {"machines": [m], "networks": []},
        }

        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            Configuration.from_dictionary(d)

        # second, programmatically we need to call finalize
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"],
                flavour="large",
                number=10,
                cluster="test-cluster",
                vcore_type="corez",
            )
        )
        with self.assertRaises(jsonschema.exceptions.ValidationError) as _:
            conf.finalize()

    def test_vcore_type_vcore_thread(self):
        # first from dict validates internally
        m: Dict = {"roles": ["r1"], "cluster": "test-cluster", "vcore_type": "thread"}
        d: Dict = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {"machines": [m], "networks": []},
        }

        conf = Configuration.from_dictionary(d)
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "thread")
        confdict = conf.to_dict()
        self.assertEqual(confdict["resources"]["machines"][-1]["vcore_type"], "thread")

        # second, programmatically we need to call finalize
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"],
                flavour="large",
                number=10,
                cluster="test-cluster",
                vcore_type="thread",
            )
        )
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "thread")

    def test_vcore_type_vcore_core(self):
        # first from dict validates internally
        m: Dict = {"roles": ["r1"], "cluster": "test-cluster", "vcore_type": "core"}
        d: Dict = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {"machines": [m], "networks": []},
        }

        conf = Configuration.from_dictionary(d)
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "core")
        confdict = conf.to_dict()
        self.assertEqual(confdict["resources"]["machines"][-1]["vcore_type"], "core")

        # second, programmatically we need to call finalize
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"],
                flavour="large",
                number=10,
                cluster="test-cluster",
                vcore_type="core",
            )
        )
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "core")

    def test_vcore_type_vcore_default(self):
        # first from dict validates internally
        m: Dict = {"roles": ["r1"], "cluster": "test-cluster"}
        d: Dict = {
            "job_name": "test-job",
            "walltime": "12:34:56",
            "resources": {"machines": [m], "networks": []},
        }

        conf = Configuration.from_dictionary(d)
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "thread")
        confdict = conf.to_dict()
        self.assertEqual(confdict["resources"]["machines"][-1]["vcore_type"], "thread")

        # second, programmatically we need to call finalize
        conf = Configuration()
        conf.add_machine_conf(
            MachineConfiguration(
                roles=["r1"],
                flavour="large",
                number=10,
                cluster="test-cluster",
            )
        )
        conf = conf.finalize()
        self.assertEqual(conf.machines[-1].vcore_type, "thread")
