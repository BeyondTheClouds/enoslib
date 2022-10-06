from typing import List, Optional
import socket

import sshtunnel
import iotlabcli.auth

from enoslib.objects import Host, DefaultNetwork
from enoslib.api import play_on
from enoslib.infra.enos_iotlab.sensor import Sensor
from enoslib.infra.enos_iotlab.iotlab_api import IotlabAPI
from enoslib.log import getLogger

logger = getLogger(__name__, ["IOTlab"])


def ssh_enabled(network_address: str) -> bool:
    return network_address.startswith("a8") or network_address.startswith("rpi")


class IotlabHost(Host):
    """
    A IoT-LAB host

    IoT-LAB has several boards with different characteristics.
    However, only A8 nodes are able to receive ssh connections
    and run linux commands.
    """

    def __init__(
        self,
        address: str,
        roles: List[str],
        site: str,
        uid: str,
        archi: str,
    ):
        super().__init__(address, user="root")
        # read only attributes
        self.roles = roles
        self.site = site
        self.uid = uid
        self.archi = archi
        self._ssh_address: Optional[str] = None

        if ssh_enabled(self.archi):
            self._ssh_address = "node-%s" % self.address

    @property
    def ssh_address(self) -> str:
        """Get an SSH reachable address for this Host.

        Returns:
            str: The address as a string.
        """
        return self._ssh_address

    def __repr__(self):
        return (
            "<IotlabHost("
            f"roles={self.roles}, "
            f"address={self.address}, "
            f"ssh_address={self.ssh_address}, "
            f"site={self.site}, "
            f"uid={self.uid})>"
        )


class IotlabSensor(Sensor):
    """A IoT-LAB sensor"""

    def __init__(
        self,
        address: str,
        roles: List[str],
        site: str,
        uid: str,
        archi: str,
        image: str,
        iotlab_client: IotlabAPI,
    ):
        alias = address.split(".")[0]
        super().__init__(address, alias)
        # read only attributes
        self.roles: List[str] = roles
        self.site: str = site
        self.uid: str = uid
        self.archi: str = archi
        self.image: str = image
        self.iotlab_client: IotlabAPI = iotlab_client

        self.user, self.passwd = iotlabcli.auth.get_user_credentials()
        self.exp_id = self.iotlab_client.get_job_id()

    def __repr__(self):
        return (
            "<IotlabSensor("
            f"roles={self.roles}, "
            f"address={self.address}, "
            f"site={self.site}, "
            f"uid={self.uid})>"
            f"image={self.image})>"
        )

    def stop(self):
        """
        Stops this sensor
        """
        self.iotlab_client.send_cmd_node(cmd="stop", nodes=[self.address])

    def start(self):
        """
        Starts this sensor
        """
        self.iotlab_client.send_cmd_node(cmd="start", nodes=[self.address])

    def reset(self):
        """
        Resets this sensor
        """
        self.iotlab_client.send_cmd_node(cmd="reset", nodes=[self.address])

    def to_dict(self):
        d = super().to_dict()
        d.update(
            roles=self.roles,
            site=self.site,
            uid=self.uid,
            archi=self.archi,
            image=self.image,
        )
        return d


class IotlabNetwork(DefaultNetwork):
    """Iotlab network class."""

    def __init__(self, roles: List[str], *args, **kargs):
        super().__init__(*args, **kargs)
        self.roles = roles


class IotlabSerial:
    def __init__(
        self,
        sensor: IotlabSensor,
        serial_port: int = 20000,
        interactive: bool = False,
        timeout: int = 5,
    ):
        """
        Create a serial connection to a sensor in IoT-LAB testbed

        The serial has 2 possibilities:
        1. Interactive: where you can interact with the serial,
        reading and sending commands to it
        2. Logging (default): only for logging purposes, collect the
        output and save it to the file (.iot-lab/<exp_id>/log/<node>-serial.log).
        No command write/read is allowed in this mode.

        More details in open_serial_conn/enable_logging methods.

        Args:
            sensor: Sensor object
            serial_port: serial port to connect to sensor
            interactive: set to true to use write/read methods
            timeout: Timeout for socket connection
        """
        self.sensor = sensor
        self.interactive = interactive
        self.serial_port = serial_port
        self.timeout = timeout
        self._serial_tunnel = None
        self._serial_socket = None
        self._filename = "~/.iot-lab/%d/log/%s_serial.log" % (
            self.sensor.exp_id,
            self.sensor.alias,
        )

    def open_serial_conn(self):
        """
        Opens serial connection to serial node.

        This method creates a SSH tunnel to frontend and a socket
        to the local port created by the SSH tunnel.

        The sshtunnel library will create a thread to do process the forwarded packets.

        Note:
            Remember to call close_serial_conn, in order to stop
            the thread and close the connection properly.
        """

        self._serial_tunnel = sshtunnel.SSHTunnelForwarder(
            self.sensor.site + ".iot-lab.info",
            ssh_username=self.sensor.user,
            ssh_password=self.sensor.passwd,
            remote_bind_address=(self.sensor.address, self.serial_port),
        )

        self._serial_tunnel.start()

        self._serial_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._serial_socket.connect(("127.0.0.1", self._serial_tunnel.local_bind_port))
        self._serial_socket.settimeout(self.timeout)

        msg = """
 IotlabSensor(%s): Opening SSH tunnel for serial connection: \
 server (%s) remote (%s:%d) local_port: %d""" % (
            self.sensor.alias,
            self.sensor.site,
            self.sensor.address,
            self.serial_port,
            self._serial_tunnel.local_bind_port,
        )

        logger.info(msg)

    def close_serial_conn(self):
        """
        Close serial connection.

        Stops thread created by sshtunnel library.
        """
        if self._serial_socket:
            self._serial_socket.close()
            self._serial_socket = None

        if self._serial_tunnel:
            self._serial_tunnel.stop()
            self._serial_tunnel = None

    def enable_logging_serial(self):
        """
        Enables logging of serial output to a file

        Runs serial_aggregator tool in frontend to write serial output
        to a file.

        Output file is saved in the experiment folder at:
        .iot-lab/<exp_id>/log/<node>-serial.log.

        Note:
            Remember to call disable_logging_serial, in order to stop
            serial_aggregator tool running on the frontend.
        """
        # convert to seconds
        timeout = self.sensor.iotlab_client.get_walltime() * 60

        with play_on(
            roles=[Host(self.sensor.site + ".iot-lab.info", user=self.sensor.user)]
        ) as p:
            cmd = "screen -dm bash -c 'serial_aggregator -l {},{} > {} 2>&1'".format(
                self.sensor.site,
                self.sensor.alias.replace("-", ","),
                self._filename,
            )
            p.shell(cmd, task_name="Running serial_aggregator", asynch=timeout, poll=0)

    def disable_logging_serial(self):
        """
        Disables logging of serial output.

        Stops serial_aggregator tool running on the frontend
        """
        with play_on(
            roles=[Host(self.sensor.site + ".iot-lab.info", user=self.sensor.user)],
            on_error_continue=True,
        ) as p:
            cmd = "pkill -f 'serial_aggregator -l {},{} > {} 2>&1'".format(
                self.sensor.site,
                self.sensor.alias.replace("-", ","),
                self._filename,
            )
            p.command(cmd, task_name="Killing serial_aggregator")

    def __enter__(self):
        if self.interactive:
            self.open_serial_conn()
        else:
            self.enable_logging_serial()

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.interactive:
            self.close_serial_conn()
        else:
            self.disable_logging_serial()

    def write(self, content: str):
        """
        Sends string on serial interface

        Args:
            content: String to be sent
        """
        if not self.interactive:
            logger.error("Not in interactive mode, impossible to write on serial")
            return

        logger.info("IotlabSerial(%s): Writing: %s", self.sensor.alias, content)
        self._serial_socket.sendall(content.encode())

    def read(self, size: int = 1024) -> str:
        """
        Reads string from serial interface

        Args:
            size: Maximum string size to be received

        Returns:
            str: String received
        """
        data = b""

        if not self.interactive:
            logger.error("Not in interactive mode, impossible to read serial")
            return data.decode()

        try:
            data = self._serial_socket.recv(size)
        except socket.timeout:
            pass
        return data.decode()


class IotlabSniffer:
    def __init__(self, sensor: IotlabSensor, timeout: int = -1):
        """
        Create a sniffer to a sensor in IoT-LAB testbed

        Runs the sniffer_aggregator tool in the frontend node
        to collect radio packets.

        Pcap is saved in the experiment folder at:
        .iot-lab/<exp_id>/sniffer/<node>.pcap.

        Args:
            sensor: Sensor object
            timeout: Timeout for sniffer_aggregator command (-1 will run
            until the experiment was finished (walltime cfg))
        """
        self.sensor = sensor
        self.timeout = timeout
        if timeout == -1:
            # convert to seconds
            self.timeout = self.sensor.iotlab_client.get_walltime() * 60
        self._filename = "~/.iot-lab/%d/sniffer/%s.pcap" % (
            self.sensor.exp_id,
            self.sensor.alias,
        )

    def start_sniffer(self):
        """
        Starts radio sniffing

        Run sniffer_aggregator tool in frontend to capture packets in
        this sniffer node. The sniffer will run for "timeout" seconds,
        or until the stop_sniffer method is called.

        Pcap is saved in the experiment folder at:
        .iot-lab/<exp_id>/sniffer/<node>.pcap.

        Note:
            Remember to call stop_sniffer, in order to stop
            sniffer_aggregator tool running on the frontend.
        """

        with play_on(
            roles=[Host(self.sensor.site + ".iot-lab.info", user=self.sensor.user)]
        ) as p:
            cmd = "sniffer_aggregator -l {},{} -o {}".format(
                self.sensor.site,
                self.sensor.alias.replace("-", ","),
                self._filename,
            )
            p.shell(
                cmd,
                task_name="Running sniffer_aggregator",
                asynch=self.timeout,
                poll=0,
            )

    def stop_sniffer(self):
        """
        Stops radio sniffing

        Kills sniffer_aggregator tool running in the frontend.
        """
        with play_on(
            roles=[Host(self.sensor.site + ".iot-lab.info", user=self.sensor.user)],
            on_error_continue=True,
        ) as p:
            cmd = 'pkill -f "%s"' % (self._filename)
            p.command(cmd, task_name="Killing sniffer_aggregator")

    def __enter__(self):
        self.start_sniffer()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.stop_sniffer()
