import pytest
from jsonschema.exceptions import ValidationError
from enoslib.infra.enos_iotlab.configuration import (
    Configuration,
    BoardConfiguration,
    PhysNodeConfiguration,
    ProfileConfiguration,
    RadioConfiguration,
    ConsumptionConfiguration,
)
import enoslib.infra.enos_iotlab.constants as constants

from enoslib.tests.unit import EnosTest


class TestConfiguration(EnosTest):
    def test_from_dictionary_minimal(self):
        d = {"resources": {"machines": [{"roles": [], "hostname": ["m3"]}]}}
        conf = Configuration.from_dictionary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)
        self.assertTrue(len(conf.machines) == 1)

    def test_from_dictionnary_minimal(self):
        d = {"resources": {"machines": [{"roles": [], "hostname": ["m3"]}]}}
        conf = Configuration.from_dictionnary(d)
        self.assertEqual(constants.DEFAULT_JOB_NAME, conf.job_name)
        self.assertEqual(constants.DEFAULT_WALLTIME, conf.walltime)
        self.assertTrue(len(conf.machines) == 1)

    def test_from_dictionary_invalid_walltime(self):
        d = {
            "walltime": "02",
            "resources": {"machines": [{"roles": [], "hostname": ["m3"]}]},
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_invalid_walltime_int(self):
        d = {
            "walltime": 20,
            "resources": {"machines": [{"roles": [], "hostname": ["m3"]}]},
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_valid_walltime(self):
        d = {
            "job_name": "test",
            "walltime": "02:00",
            "resources": {"machines": [{"roles": [], "hostname": ["m3"]}]},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("test", conf.job_name)
        self.assertEqual("02:00", conf.walltime)

    def test_from_dictionary_valid_walltime_more1day(self):
        d = {
            "job_name": "test",
            "walltime": "1232:00",
            "resources": {"machines": [{"roles": [], "hostname": ["m3"]}]},
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual("test", conf.job_name)
        self.assertEqual("1232:00", conf.walltime)

    def test_from_dictionary_invalid_boards_missing_site(self):
        d = {
            "resources": {
                "machines": [{"roles": ["r1"], "archi": "m3:at86rf231", "nodes": 2}],
            }
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_invalid_boards_missing_archi(self):
        d = {
            "resources": {
                "machines": [{"roles": ["r1"], "site": "grenoble", "number": 2}],
            }
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_invalid_boards_missing_roles(self):
        d = {
            "resources": {
                "machines": [
                    {"archi": "m3:at86rf231", "site": "grenoble", "number": 2}
                ],
            }
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_valid_boards(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                    }
                ],
            }
        }
        conf = Configuration.from_dictionary(d)
        self.assertTrue(len(conf.machines) == 1)
        self.assertEqual(d["resources"]["machines"][0]["archi"], conf.machines[0].archi)
        self.assertEqual(d["resources"]["machines"][0]["site"], conf.machines[0].site)
        self.assertEqual(
            d["resources"]["machines"][0]["number"], conf.machines[0].number
        )

    def test_from_dictionary_valid_2boards(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                    },
                    {"roles": ["r1"], "archi": "m3:at86rf231", "site": "grenoble"},
                ],
            }
        }
        conf = Configuration.from_dictionary(d)
        self.assertTrue(len(conf.machines) == 2)

    def test_from_dictionary_invalid_phys_nodes_missing_hostname(self):
        d = {
            "resources": {
                "machines": [{"roles": ["r1"]}],
            }
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_from_dictionary_valid_phys_nodes(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "hostname": [
                            "m3-1.grenoble.iot-lab.info",
                            "m3-2.grenoble.iot-lab.info",
                        ],
                        "image": "test.elf",
                    }
                ],
            }
        }
        conf = Configuration.from_dictionary(d)
        self.assertTrue(len(conf.machines[0].hostname) == 2)
        self.assertEqual(
            d["resources"]["machines"][0]["hostname"][0], conf.machines[0].hostname[0]
        )
        self.assertEqual(
            d["resources"]["machines"][0]["hostname"][1], conf.machines[0].hostname[1]
        )
        self.assertEqual(d["resources"]["machines"][0]["image"], conf.machines[0].image)

    def test_invalid_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(
            BoardConfiguration(
                roles=["r2"], archi="m3:at86rf231", site="grenoble", number=10
            )
        ).add_machine_conf(
            PhysNodeConfiguration(roles=["r2"], hostname=["m3-1.grenoble.iot-lab.info"])
        )
        with self.assertRaises(ValidationError):
            conf.finalize()

    def test_invalid_programmatic_image(self):
        conf = Configuration()
        conf.add_machine_conf(
            BoardConfiguration(
                roles=["r2"],
                archi="m3:at86rf231",
                site="grenoble",
                number=10,
                image=3,
            )
        )
        with self.assertRaises(ValidationError):
            conf.finalize()

    def test_board_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(
            BoardConfiguration(
                roles=["r2"],
                archi="m3:at86rf231",
                site="grenoble",
                number=10,
                image="test.elf",
            )
        ).add_machine_conf(
            BoardConfiguration(
                roles=["r1"], archi="m3:at86rf231", site="grenoble", number=10
            )
        )
        conf.finalize()

        self.assertEqual(2, len(conf.machines))
        self.assertEqual(conf.machines[0].image, "test.elf")

    def test_phys_programmatic(self):
        conf = Configuration()
        conf.add_machine_conf(
            PhysNodeConfiguration(roles=["r2"], hostname=["m3-1.grenoble.iot-lab.info"])
        ).add_machine_conf(
            PhysNodeConfiguration(roles=["r1"], hostname=["m3-2.grenoble.iot-lab.info"])
        )
        conf.finalize()

        self.assertEqual(2, len(conf.machines))

    def test_add_machine_phys(self):
        conf = Configuration()
        conf.add_machine(roles=["r2"], hostname=["m3-1.grenoble.iot-lab.info"])
        conf.finalize()

        self.assertEqual(1, len(conf.machines))

    def test_add_machine_board(self):
        conf = Configuration()
        conf.add_machine(roles=["r1"], archi="m3:at86rf231", site="grenoble", number=10)
        conf.finalize()

        self.assertEqual(1, len(conf.machines))

    def test_profile_wrong_no_name(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                        "profile": "test_profile",
                    }
                ],
            },
            "monitoring": {
                "profiles": [
                    {
                        "archi": "m3",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 0,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_profile_wrong_archi(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                        "profile": "test_profile",
                    }
                ],
            },
            "monitoring": {
                "profiles": [
                    {
                        "name": "test_profile",
                        "archi": "test_archi",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 0,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }
        with self.assertRaises(ValidationError):
            Configuration.from_dictionary(d)

    def test_profile_radio_dict(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                        "profile": "test_profile",
                    }
                ],
            },
            "monitoring": {
                "profiles": [
                    {
                        "name": "test_profile",
                        "archi": "m3",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 0,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(conf.machines[0].profile, "test_profile")
        self.assertEqual(conf.profiles[0].name, d["monitoring"]["profiles"][0]["name"])
        self.assertEqual(
            conf.profiles[0].archi, d["monitoring"]["profiles"][0]["archi"]
        )
        self.assertEqual(
            conf.profiles[0].radio.mode, d["monitoring"]["profiles"][0]["radio"]["mode"]
        )
        self.assertEqual(
            conf.profiles[0].radio.num_per_channel,
            d["monitoring"]["profiles"][0]["radio"]["num_per_channel"],
        )
        self.assertEqual(
            conf.profiles[0].radio.channels,
            d["monitoring"]["profiles"][0]["radio"]["channels"],
        )

    def test_profile_consumption_dict(self):
        d = {
            "resources": {
                "machines": [
                    {
                        "roles": ["r1"],
                        "archi": "m3:at86rf231",
                        "site": "grenoble",
                        "number": 2,
                    }
                ],
            },
            "monitoring": {
                "profiles": [
                    {
                        "name": "test_profile",
                        "archi": "a8",
                        "consumption": {
                            "current": True,
                            "power": True,
                            "voltage": True,
                            "period": 140,
                            "average": 16,
                        },
                    }
                ],
            },
        }
        conf = Configuration.from_dictionary(d)
        self.assertEqual(conf.profiles[0].name, d["monitoring"]["profiles"][0]["name"])
        self.assertEqual(
            conf.profiles[0].archi, d["monitoring"]["profiles"][0]["archi"]
        )
        self.assertEqual(
            conf.profiles[0].consumption.current,
            d["monitoring"]["profiles"][0]["consumption"]["current"],
        )
        self.assertEqual(
            conf.profiles[0].consumption.power,
            d["monitoring"]["profiles"][0]["consumption"]["power"],
        )
        self.assertEqual(
            conf.profiles[0].consumption.voltage,
            d["monitoring"]["profiles"][0]["consumption"]["voltage"],
        )
        self.assertEqual(
            conf.profiles[0].consumption.period,
            d["monitoring"]["profiles"][0]["consumption"]["period"],
        )
        self.assertEqual(
            conf.profiles[0].consumption.average,
            d["monitoring"]["profiles"][0]["consumption"]["average"],
        )

    def test_profile_prog(self):
        profile_name = "test_profile"
        conf = Configuration()
        conf.add_machine_conf(
            PhysNodeConfiguration(
                roles=["r2"],
                hostname=["m3-1.grenoble.iot-lab.info"],
                image="test_profile",
            )
        ).add_profile(
            name=profile_name,
            archi="m3",
            radio=RadioConfiguration(mode="rssi", num_per_channel=0, channels=[11]),
            consumption=ConsumptionConfiguration(
                current=False, power=False, voltage=False, period=140, average=16
            ),
        )
        conf.finalize()
