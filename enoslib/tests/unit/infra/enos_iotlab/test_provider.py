# -*- coding: utf-8 -*-
import mock
import tempfile
from unittest.mock import patch
from enoslib.errors import NegativeWalltime

from enoslib.infra.enos_iotlab.provider import Iotlab
from enoslib.infra.enos_iotlab.error import EnosIotlabCfgError

from enoslib.infra.enos_iotlab.constants import DEFAULT_JOB_NAME, PROD
from enoslib.infra.enos_iotlab.configuration import (
    Configuration,
    BoardConfiguration,
    PhysNodeConfiguration,
    NetworkConfiguration,
)
from ipaddress import (
    IPv4Network,
    IPv6Network,
)
from enoslib.tests.unit import EnosTest

from iotlabcli.experiment import AliasNodes, exp_resources
from iotlabcli.profile import ProfileM3, ProfileA8, ProfileCustom


class TestAuthProvider(EnosTest):
    @patch("iotlabcli.auth.get_user_credentials")
    def test_missing_iotlab_cfg(self, MockApi):
        provider_config = Configuration().add_machine_conf(
            BoardConfiguration(
                roles=["r2"], archi="m3:at86rf231", site="grenoble", number=1
            )
        )
        MockApi.return_value = [None, None]
        # build a provider
        with self.assertRaises(EnosIotlabCfgError):
            Iotlab(provider_config)

    @patch("iotlabcli.rest.Api")
    @patch("iotlabcli.auth.get_user_credentials")
    def test_valid_init(self, cred, api):
        provider_config = Configuration().add_machine_conf(
            BoardConfiguration(
                roles=["r2"], archi="m3:at86rf231", site="grenoble", number=1
            )
        )
        cred.return_value = ["test", "test"]
        # build a provider
        Iotlab(provider_config)
        api.assert_called_once()


class TestSubmit(EnosTest):
    def setUp(self):
        # initialize common mocks for tests
        mock_api = mock.patch("iotlabcli.rest.Api").start()
        mock_api.return_value = None

        mock_auth = mock.patch("iotlabcli.auth.get_user_credentials").start()
        mock_auth.return_value = ["test", "test"]

        mock_wait = mock.patch("iotlabcli.experiment.wait_experiment").start()
        mock_wait.return_value = None

        mock_get_list = mock.patch("iotlabcli.experiment.get_experiments_list").start()
        mock_get_list.return_value = {"items": []}

        mock_wait_a8 = mock.patch("iotlabsshcli.open_linux.wait_for_boot").start()
        mock_wait_a8.return_value = {"wait-for-boot": {"0": [], "1": []}}

        mock_get = mock.patch("iotlabcli.experiment.get_experiment").start()
        mock_get.return_value = {
            "items": [
                {
                    "site": "grenoble",
                    "archi": "a8:at86rf231",
                    "uid": "b564",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "a8-1.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                }
            ]
        }

    def tearDown(self):
        mock.patch.stopall()

    @patch("iotlabcli.experiment.submit_experiment")
    @patch("iotlabcli.experiment.get_experiments_list")
    def test_valid_job_already_running(self, mock_get_list, mock_submit):
        provider_config = (
            Configuration()
            .from_settings(job_name="EnOSlib2")
            .add_machine_conf(
                BoardConfiguration(
                    roles=["r2"], archi="a8:at86rf231", site="grenoble", number=1
                )
            )
        )
        mock_get_list.return_value = {
            "items": [
                {
                    "id": 237466,
                    "name": "EnOSlib2",
                    "user": "donassol",
                    "state": "Running",
                    "submission_date": "2020-11-30T09:58:28Z",
                    "start_date": "2020-11-30T09:58:30Z",
                    "stop_date": "1970-01-01T00:00:00Z",
                    "effective_duration": 10,
                    "submitted_duration": 120,
                    "nb_nodes": 1,
                    "scheduled_date": "2020-11-30T09:58:30Z",
                }
            ]
        }
        # build a provider
        p = Iotlab(provider_config)
        nodes, _ = p.init()
        mock_submit.assert_not_called()
        self.assertTrue(len(nodes["r2"]) == 1)

    @patch("iotlabcli.experiment.submit_experiment")
    @patch("iotlabcli.experiment.get_experiment")
    def test_01_valid_board_cfg(self, mock_get, mock_submit):
        provider_config = Configuration().add_machine_conf(
            BoardConfiguration(
                roles=["r2"], archi="a8:at86rf231", site="grenoble", number=2
            )
        )
        mock_get.return_value = {
            "items": [
                {
                    "site": "grenoble",
                    "archi": "a8:at86rf231",
                    "uid": "b564",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "a8-1.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
                {
                    "site": "grenoble",
                    "archi": "a8:at86rf231",
                    "uid": "b565",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "a8-2.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
            ]
        }
        # build a provider
        p = Iotlab(provider_config)
        nodes, networks = p.init()
        mock_submit.assert_called_with(
            api=mock.ANY,
            name=DEFAULT_JOB_NAME,
            duration=1,
            start_time = None,
            resources=[
                exp_resources(
                    AliasNodes(2, site="grenoble", archi="a8:at86rf231", _alias=1)
                )
            ],
        )  # not ideal but the _alias depends on the test order...
        self.assertEquals(2, len(nodes["r2"]))
        self.assertTrue(len(networks) == 1)
        self.assertIsInstance(networks[PROD][0].network, IPv4Network)
        self.assertIsInstance(networks[PROD][1].network, IPv6Network)

    @patch("iotlabcli.experiment.submit_experiment")
    def test_valid_phys_cfg(self, mock_submit):
        list_nodes = ["a8-1.grenoble.iot-lab.info"]
        provider_config = Configuration().add_machine_conf(
            PhysNodeConfiguration(roles=[], hostname=list_nodes)
        )
        # build a provider
        p = Iotlab(provider_config)
        nodes, _ = p.init()
        mock_submit.assert_called_with(
            api=mock.ANY,
            name=DEFAULT_JOB_NAME,
            duration=1,
            start_time = None,
            resources=[exp_resources(list_nodes)],
        )
        self.assertEquals(nodes, {})  # no roles nothing to check

    @patch("iotlabcli.experiment.stop_experiment")
    def test_destroy_not_init(self, mock_stop):
        list_nodes = ["a8-1.grenoble.iot-lab.info"]
        provider_config = Configuration().add_machine_conf(
            PhysNodeConfiguration(roles=[], hostname=list_nodes)
        )
        # build a provider
        p = Iotlab(provider_config)
        p.destroy()  # nothing happens
        mock_stop.assert_not_called()

    @patch("iotlabcli.experiment.submit_experiment")
    @patch("iotlabcli.experiment.stop_experiment")
    def test_destroy_init(self, mock_stop, mock_submit):
        list_nodes = ["a8-1.grenoble.iot-lab.info"]
        provider_config = Configuration().add_machine_conf(
            PhysNodeConfiguration(roles=[], hostname=list_nodes)
        )
        # build a provider
        mock_submit.return_value = {"id": 666}
        p = Iotlab(provider_config)
        p.init()
        p.destroy()
        mock_stop.assert_called_with(api=mock.ANY, exp_id=666)

    @patch("iotlabcli.experiment.submit_experiment")
    def test_deploy_with_network(self, mock_submit):
        list_nodes = ["a8-1.grenoble.iot-lab.info"]
        provider_config = (
            Configuration()
            .add_machine_conf(PhysNodeConfiguration(roles=[], hostname=list_nodes))
            .add_network_conf(
                NetworkConfiguration(
                    net_id="network1",
                    roles=["n1"],
                    net_type="prod",
                    site="Grenoble",
                )
            )
        )
        # build a provider
        p = Iotlab(provider_config)
        nodes, networks = p.init()
        self.assertTrue(len(networks) == 1)
        self.assertTrue(len(networks["n1"]) == 2)


class TestDeploy(EnosTest):
    def setUp(self):
        # initialize common mocks for tests
        mock_api = mock.patch("iotlabcli.rest.Api").start()
        mock_api.return_value = None

        mock_auth = mock.patch("iotlabcli.auth.get_user_credentials").start()
        mock_auth.return_value = ["test", "test"]

        mock_wait = mock.patch("iotlabcli.experiment.wait_experiment").start()
        mock_wait.return_value = None

        mock_wait_a8 = mock.patch("iotlabsshcli.open_linux.wait_for_boot").start()
        mock_wait_a8.return_value = {"wait-for-boot": {"0": [], "1": []}}

        mock_get_list = mock.patch("iotlabcli.experiment.get_experiments_list").start()
        mock_get_list.return_value = {"items": []}

        mock_submit = mock.patch("iotlabcli.experiment.submit_experiment").start()
        mock_submit.return_value = {"id": 666}

        mock_get = mock.patch("iotlabcli.experiment.get_experiment").start()
        mock_get.return_value = {
            "items": [
                {
                    "site": "grenoble",
                    "archi": "m3:at86rf231",
                    "uid": "b564",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "m3-1.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
                {
                    "site": "grenoble",
                    "archi": "m3:at86rf231",
                    "uid": "b565",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "m3-2.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
            ]
        }

    def tearDown(self):
        mock.patch.stopall()

    @patch("iotlabcli.node.node_command")
    def test_deploy(self, mock_node):
        list_nodes = ["m3-1.grenoble.iot-lab.info"]
        provider_config = (
            Configuration()
            .add_machine_conf(
                PhysNodeConfiguration(roles=[], hostname=list_nodes, image="test.elf"),
            )
            .add_machine_conf(
                PhysNodeConfiguration(
                    roles=["r2"], hostname=["m3-2.grenoble.iot-lab.info"]
                )
            )
        )
        # build a provider
        p = Iotlab(provider_config)
        nodes, _ = p.init()
        mock_node.assert_called_with(
            api=mock.ANY,
            command="flash",
            exp_id=666,
            nodes_list=list_nodes,
            cmd_opt="test.elf",
        )
        self.assertTrue(len(nodes) == 1)
        self.assertTrue(len(nodes["r2"]) == 1)

    @patch("iotlabcli.experiment.get_experiment")
    @patch("iotlabsshcli.open_linux.wait_for_boot")
    def test_wait_a8(self, mock_wait_a8, mock_get):
        list_nodes = ["a8-1.grenoble.iot-lab.info"]
        provider_config = Configuration().add_machine_conf(
            PhysNodeConfiguration(roles=[], hostname=list_nodes)
        )
        # build a provider
        mock_get.return_value = {
            "items": [
                {
                    "site": "grenoble",
                    "archi": "a8:at86rf231",
                    "uid": "b564",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "a8-1.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                }
            ]
        }
        p = Iotlab(provider_config)
        nodes, _ = p.init()
        mock_wait_a8.assert_called_with(
            {"user": "test", "exp_id": 666}, ["node-%s" % n for n in list_nodes]
        )

    @patch("iotlabsshcli.open_linux.wait_for_boot")
    def test_no_wait_a8(self, mock_wait_a8):
        provider_config = (
            Configuration()
            .add_machine_conf(
                PhysNodeConfiguration(
                    roles=[], hostname=["m3-1.grenoble.iot-lab.info"]
                ),
            )
            .add_machine_conf(
                PhysNodeConfiguration(
                    roles=["r2"], hostname=["m3-2.grenoble.iot-lab.info"]
                )
            )
        )
        # build a provider
        p = Iotlab(provider_config)
        nodes, _ = p.init()
        mock_wait_a8.assert_not_called()


class TestProfiles(EnosTest):
    def setUp(self):
        mock_api = mock.patch("iotlabcli.rest.Api").start()
        mock_api.return_value.get_profiles.return_value = []

        # initialize common mocks for tests
        mock_auth = mock.patch("iotlabcli.auth.get_user_credentials").start()
        mock_auth.return_value = ["test", "test"]

        mock_wait = mock.patch("iotlabcli.experiment.wait_experiment").start()
        mock_wait.return_value = None

        mock_wait_a8 = mock.patch("iotlabsshcli.open_linux.wait_for_boot").start()
        mock_wait_a8.return_value = {"wait-for-boot": {"0": [], "1": []}}

        mock_get_list = mock.patch("iotlabcli.experiment.get_experiments_list").start()
        mock_get_list.return_value = {"items": []}

        mock_submit = mock.patch("iotlabcli.experiment.submit_experiment").start()
        mock_submit.return_value = {"id": 666}

        mock_get = mock.patch("iotlabcli.experiment.get_experiment").start()
        mock_get.return_value = {
            "items": [
                {
                    "site": "grenoble",
                    "archi": "m3:at86rf231",
                    "uid": "b564",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "m3-1.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
                {
                    "site": "grenoble",
                    "archi": "m3:at86rf231",
                    "uid": "b565",
                    "x": "20.33",
                    "state": "Alive",
                    "network_address": "m3-2.grenoble.iot-lab.info",
                    "z": "2.63",
                    "production": "YES",
                    "y": "25.28",
                    "mobile": "0",
                    "mobility_type": " ",
                    "camera": None,
                },
            ]
        }

    def tearDown(self):
        mock.patch.stopall()

    @patch("iotlabcli.experiment.submit_experiment")
    @patch("iotlabcli.rest.Api")
    def test_02_radio(self, mock_api, mock_submit):
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
                            "num_per_channel": 1,
                            "period": 1,
                            "channels": [11, 26],
                        },
                    }
                ],
            },
        }
        # building profile as expected by cli-tools
        profile = ProfileM3(
            profilename="test_profile",
            power="dc",
        )
        profile.set_radio(
            mode="rssi",
            channels=[11, 26],
            period=1,
            num_per_channel=1,
        )

        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        mock_submit.assert_called_with(
            api=mock.ANY,
            name=DEFAULT_JOB_NAME,
            duration=1,
            start_time = None,
            resources=[
                exp_resources(
                    AliasNodes(2, site="grenoble", archi="m3:at86rf231", _alias=2),
                    profile_name="test_profile",
                )  # not ideal but the _alias depends on the test order...
            ],
        )
        mock_api.return_value.add_profile.assert_called_with(profile)

    @patch("iotlabcli.rest.Api")
    def test_consumption(self, mock_api):
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
                ]
            },
        }
        # building profile as expected by cli-tools
        profile = ProfileA8(
            profilename="test_profile",
            power="dc",
        )
        profile.set_consumption(
            period=140,
            average=16,
            power=True,
            voltage=True,
            current=True,
        )

        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        mock_api.return_value.add_profile.assert_called_with(profile)

    @patch("iotlabcli.rest.Api")
    def test_custom_radio_consumption(self, mock_api):
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
                        "archi": "custom",
                        "consumption": {
                            "current": True,
                            "power": True,
                            "voltage": True,
                            "period": 140,
                            "average": 16,
                        },
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 1,
                            "period": 1,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }
        # building profile as expected by cli-tools
        profile = ProfileCustom(
            profilename="test_profile",
            power="dc",
        )
        profile.set_consumption(
            period=140,
            average=16,
            power=True,
            voltage=True,
            current=True,
        )
        profile.set_radio(
            mode="rssi",
            channels=[11, 26],
            period=1,
            num_per_channel=1,
        )

        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        mock_api.return_value.add_profile.assert_called_with(profile)

    @patch("iotlabcli.rest.Api")
    def test_del_profile(self, mock_api):
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
                        "archi": "m3",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 1,
                            "period": 1,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }

        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        p.destroy()
        mock_api.return_value.del_profile.assert_called_with(name="test_profile")

    @patch("iotlabcli.rest.Api")
    def test_profile_already_created(self, mock_api):
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
                        "archi": "m3",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 1,
                            "period": 1,
                            "channels": [11, 26],
                        },
                    }
                ]
            },
        }
        mock_api.return_value.get_profiles.return_value = [
            {
                "nodearch": "m3",
                "power": "dc",
                "profilename": "test_profile",
                "radio": {
                    "channels": [11, 14],
                    "mode": "rssi",
                    "num_per_channel": 1,
                    "period": 1,
                },
            }
        ]
        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        mock_api.return_value.add_profile.assert_not_called()

    @patch("iotlabcli.rest.Api")
    def test_multiple_profiles(self, mock_api):
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
                        "archi": "m3",
                        "radio": {
                            "mode": "rssi",
                            "num_per_channel": 1,
                            "period": 1,
                            "channels": [11, 26],
                        },
                    },
                    {
                        "name": "test_profile2",
                        "archi": "a8",
                        "consumption": {
                            "current": True,
                            "power": True,
                            "voltage": True,
                            "period": 140,
                            "average": 16,
                        },
                    },
                ]
            },
        }
        # building profile as expected by cli-tools
        profile = ProfileM3(
            profilename="test_profile",
            power="dc",
        )
        profile.set_radio(
            mode="rssi",
            channels=[11, 26],
            period=1,
            num_per_channel=1,
        )
        profile2 = ProfileA8(
            profilename="test_profile2",
            power="dc",
        )
        profile2.set_consumption(
            period=140,
            average=16,
            power=True,
            voltage=True,
            current=True,
        )

        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        mock_api.return_value.add_profile.assert_has_calls(
            [mock.call(profile), mock.call(profile2)], any_order=True
        )

    @patch("enoslib.api.play_on.__enter__")
    @patch("enoslib.api.play_on.__exit__")
    @patch("iotlabcli.rest.Api")
    def test_collect_data(self, mock_api, mock_exit, mock_enter):
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
        }
        conf = Configuration.from_dictionary(d)
        p = Iotlab(conf)
        nodes, _ = p.init()
        my_m = mock.Mock()
        mock_enter.return_value = my_m
        mock_api.return_value.get_experiment_info.return_value = b"test"
        with tempfile.TemporaryDirectory() as tmpdir:
            p.collect_data_experiment(tmpdir)
            mock_api.return_value.get_experiment_info.assert_called_with(
                expid=666, option="data"
            )
            my_m.fetch.assert_called_with(
                src=".iot-lab/666-{{ inventory_hostname }}.tar.gz",
                dest=tmpdir + "/",
                flat=True,
            )
            my_m.shell.assert_has_calls(
                [
                    mock.call(
                        "cd .iot-lab/; tar --ignore-command-error -czf 666-{{ inventory_hostname }}.tar.gz 666/"
                    ),
                    mock.call(
                        "cd .iot-lab/; rm -f 666-{{ inventory_hostname }}.tar.gz"
                    ),
                ],
                any_order=True,
            )
    
    def test_offset_walltime(self):
        conf = Configuration()
        conf.walltime = "02:00"
        with patch.object(Configuration,'finalize',return_value=conf) as patch_finalize:
            provider = Iotlab(conf)
            provider.offset_walltime(-3600)
            self.assertEquals(provider.provider_conf.walltime,"01:00")
        
    def test_offset_walltime_negative_walltime(self):
        conf = Configuration()
        conf.walltime = "02:00"
        with patch.object(Configuration,'finalize',return_value=conf) as patch_finalize:
            provider = Iotlab(conf)
            with self.assertRaises(NegativeWalltime):
                provider.offset_walltime(-7200)
        
