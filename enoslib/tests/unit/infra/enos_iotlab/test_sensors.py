# -*- coding: utf-8 -*-
import mock
from unittest.mock import patch

from enoslib.infra.enos_iotlab.objects import (
    IotlabSensor,
    IotlabSerial,
    IotlabSniffer,
    )
from enoslib.infra.enos_iotlab.iotlab_api import IotlabAPI

from enoslib.tests.unit import EnosTest


class TestSensors(EnosTest):

    def setUp(self):
        # initialize common mocks for tests
        mock_auth = mock.patch('iotlabcli.auth.get_user_credentials').start()
        mock_auth.return_value = ["test", "test"]

        self.client = IotlabAPI()
        self.client.job_id = 666
        self.client.walltime = 10

    def tearDown(self):
        mock.patch.stopall()

    @patch('iotlabcli.node.node_command')
    def test_start(self, mock_node):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        sensor.start()
        mock_node.assert_called_with(
            api=mock.ANY, command="start", exp_id=666, nodes_list=[node_addr])

    @patch('iotlabcli.node.node_command')
    def test_reset(self, mock_node):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        sensor.reset()
        mock_node.assert_called_with(
            api=mock.ANY, command="reset", exp_id=666, nodes_list=[node_addr])

    @patch('iotlabcli.node.node_command')
    def test_stop(self, mock_node):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        sensor.stop()
        mock_node.assert_called_with(
            api=mock.ANY, command="stop", exp_id=666, nodes_list=[node_addr])


class TestSerial(EnosTest):

    def setUp(self):
        # initialize common mocks for tests
        mock_tunnel = mock.patch('sshtunnel.SSHTunnelForwarder').start()
        mock_tunnel.local_bind_port = 666

        mock_auth = mock.patch('iotlabcli.auth.get_user_credentials').start()
        mock_auth.return_value = ["test", "test"]

        self.client = IotlabAPI()
        self.client.job_id = 666
        self.client.walltime = 10

    def tearDown(self):
        mock.patch.stopall()

    @patch('socket.socket')
    @patch('sshtunnel.SSHTunnelForwarder')
    def test_open_close_conn(self, mock_tunnel, mock_sock):
        sensor = IotlabSensor(
            address="m3-1.grenoble.iot-lab.info",
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )

        with IotlabSerial(sensor, interactive=True, timeout=10):
            # check open_conn calls
            mock_tunnel.assert_called_with(
                "grenoble.iot-lab.info",
                ssh_username="test",
                ssh_password="test",
                remote_bind_address=("m3-1.grenoble.iot-lab.info", 20000),
            )
            mock_sock.return_value.connect.assert_called_with(("127.0.0.1", mock.ANY))
            mock_sock.return_value.settimeout.assert_called_with(10)
        # check close_conn calls
        mock_sock.return_value.close.assert_called_once()
        mock_tunnel.return_value.stop.assert_called_once()

    @patch('socket.socket')
    def test_write_not_open(self, mock_sock):
        sensor = IotlabSensor(
            address="m3-1.grenoble.iot-lab.info",
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        serial = IotlabSerial(sensor)

        serial.write("test")
        mock_sock.return_value.sendall.assert_not_called()

    @patch('socket.socket')
    def test_write(self, mock_sock):
        sensor = IotlabSensor(
            address="m3-1.grenoble.iot-lab.info",
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        with IotlabSerial(sensor, interactive=True) as serial:
            test_str = "test"
            serial.write(test_str)
            mock_sock.return_value.sendall.assert_called_with(test_str.encode())

    @patch('socket.socket')
    def test_read_not_open(self, mock_sock):
        sensor = IotlabSensor(
            address="m3-1.grenoble.iot-lab.info",
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )

        serial = IotlabSerial(sensor)
        data = serial.read()
        mock_sock.return_value.recv.assert_not_called()
        self.assertEqual(data, "")

    @patch('socket.socket')
    def test_read(self, mock_sock):
        sensor = IotlabSensor(
            address="m3-1.grenoble.iot-lab.info",
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        with IotlabSerial(sensor, interactive=True) as serial:
            test_str = "test"
            mock_sock.return_value.recv.return_value = test_str.encode()

            data = serial.read(32)
            mock_sock.return_value.recv.assert_called_with(32)
            self.assertEqual(data, test_str)

    @patch('enoslib.api.play_on.__enter__')
    @patch('enoslib.api.play_on.__exit__')
    def test_serial_logging(self, mock_exit, mock_enter):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        my_m = mock.Mock()
        mock_enter.return_value = my_m
        with IotlabSerial(sensor):
            my_m.shell.assert_called_with(
                "screen -dm bash -c 'serial_aggregator -l grenoble,m3,1 > ~/.iot-lab/666/log/m3-1_serial.log 2>&1'",
                display_name=mock.ANY, asynch=10 * 60, poll=0)

        my_m.command.assert_called_with(
            "pkill -f 'serial_aggregator -l grenoble,m3,1 > ~/.iot-lab/666/log/m3-1_serial.log 2>&1'",
            display_name=mock.ANY)


class TestSniffer(EnosTest):

    def setUp(self):
        # initialize common mocks for tests
        mock_auth = mock.patch('iotlabcli.auth.get_user_credentials').start()
        mock_auth.return_value = ["test", "test"]

        self.client = IotlabAPI()
        self.client.job_id = 666
        self.client.walltime = 10

    def tearDown(self):
        mock.patch.stopall()

    @patch('enoslib.api.play_on.__enter__')
    @patch('enoslib.api.play_on.__exit__')
    def test_start_sniffer(self, mock_exit, mock_enter):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        my_m = mock.Mock()
        mock_enter.return_value = my_m
        with IotlabSniffer(sensor, timeout=100):
            my_m.shell.assert_called_with(
                "sniffer_aggregator -l grenoble,m3,1 -o ~/.iot-lab/666/sniffer/m3-1.pcap",
                display_name=mock.ANY, asynch=100, poll=0)

    @patch('enoslib.api.play_on.__enter__')
    @patch('enoslib.api.play_on.__exit__')
    def test_stop_sniffer(self, mock_exit, mock_enter):
        node_addr = "m3-1.grenoble.iot-lab.info"
        sensor = IotlabSensor(
            address=node_addr,
            roles=["sensor"],
            site="grenoble",
            uid="b413",
            archi="m3:at86rf231",
            image="",
            iotlab_client=self.client,
        )
        my_m = mock.Mock()
        mock_enter.return_value = my_m
        with IotlabSniffer(sensor, timeout=100):
            pass

        my_m.command.assert_called_with(
            'pkill -f "~/.iot-lab/666/sniffer/m3-1.pcap"',
            display_name=mock.ANY)