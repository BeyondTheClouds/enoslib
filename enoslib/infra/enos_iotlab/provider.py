from datetime import datetime, time, timezone
import pathlib
import re
from typing import List, Optional, Tuple
from urllib.error import HTTPError

import iotlabcli.auth

from enoslib.api import play_on, run, CommandResult, CustomCommandResult
from enoslib.errors import (
    InvalidReservationCritical,
    InvalidReservationTime,
    InvalidReservationTooOld,
    NegativeWalltime,
)
from enoslib.objects import Host, Networks, Roles
from enoslib.infra.provider import Provider
from enoslib.infra.enos_iotlab.iotlab_api import IotlabAPI, test_slot
from enoslib.infra.enos_iotlab.objects import (
    IotlabHost,
    IotlabSensor,
    IotlabNetwork,
    ssh_enabled,
)
from enoslib.infra.utils import mk_pools, pick_things

from enoslib.infra.enos_iotlab.constants import PROD
from enoslib.infra.enos_iotlab.configuration import (
    PhysNodeConfiguration,
)
from enoslib.log import getLogger

logger = getLogger(__name__, ["IOTlab"])


def check():
    statuses = []
    iotlab_user = None
    try:
        iotlab_user, _ = iotlabcli.auth.get_user_credentials()
    except Exception as e:
        statuses.append(("api:conf", False, str(e)))
        return statuses
    statuses.append(("api:conf", True, ""))

    access = Host("grenoble.iot-lab.info", user=iotlab_user)
    # beware: on access the homedir isn't writable (so using raw)
    r = run(
        "hostname",
        access,
        raw=True,
        on_error_continue=True,
        task_name=f"Connecting to {iotlab_user}@{access.alias}",
    )
    if isinstance(r[0], CommandResult):
        statuses.append(
            ("ssh:access", r[0].rc == 0, r[0].stderr if r[0].rc != 0 else "")
        )
    elif isinstance(r[0], CustomCommandResult):
        # hostname don't fail so if we get an error at this point
        # it's because of the connection
        # The result in this case is a CustomCommandResult
        # see:
        # CustomCommandResult(host='acces.grid5000.fr', task='Connecting to
        # msimonin@acces.grid5000.fr', status='UNREACHABLE',
        # payload={'unreachable': True, 'msg': 'Failed to connect to the host
        # via ssh: channel 0: open failed: administratively prohibited: open
        # failed\r\nstdio forwarding failed\r\nssh_exchange_identification:
        # Connection closed by remote host', 'changed': False})
        statuses.append(("ssh:access", False, r[0].payload["msg"]))
    else:
        raise ValueError("Impossible command result type received, this is a bug")

    try:
        api = IotlabAPI()
        api.healthcheck()
        statuses.append(("api:access", True, ""))
    except Exception as e:
        statuses.append(("api:access", False, str(e)))

    return statuses


class Iotlab(Provider):
    """
    The provider to be used when deploying on FIT/IoT-LAB testbed

    Args:
        provider_conf (iotlab.Configuration): Configuration file for IoT-LAB platform
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider_conf = self.provider_conf.finalize()
        self.client = IotlabAPI()
        self.hosts: List[IotlabHost] = []
        self.sensors: List[IotlabSensor] = []
        self.networks: List[IotlabNetwork] = []
        self.nodes_status = None
        self.experiments_status = None

    def init(
        self, start_time: Optional[int] = None, force_deploy: bool = False, **kwargs
    ) -> Tuple[Roles, Networks]:
        """
        Take ownership over FIT/IoT-LAB resources

        Check if job is already running in the testbed
        (based on the name given on config).
        Set the reservation to start_time if provided
        Submit a new job if necessary and wait its initialization.
        Return inventory of resources allocated.

        Returns:
            (roles, dict): representing the inventory of resources.
        Raises:
            InvalidReservationTime: If the set reservation_date from
            provider.conf isn't free
            InvalidReservationOld: If the set reservation_date from
            provider.conf is in the past
            InvalidReservationCritical: Any other error that might
            occur during the reservation
        """
        if start_time:
            self.set_reservation(start_time)
        self._profiles()
        self._reserve()
        self._deploy()

        return self._to_enoslib()

    def async_init(self, start_time: Optional[int] = None, **kwargs):
        if start_time:
            self.set_reservation(start_time)
        self._profiles()
        self._reserve(wait=False)

    def collect_data_experiment(self, exp_dir: Optional[str] = None):
        """
        Collects data about experiment from frontends

        During the experiment, FIT/IoT-LAB collects and saves a lot of data
        about it under the folder ~/.iot-lab/.
        This method will connect to each frontend used during the test
        (grenoble, paris, etc), will compress and fetch this data.

        2 kinds of information are collected:
        1. REST API, about experiment: saved as <exp_id>.tar.gz

        2. .iot-lab/, from each frontend: saved as <exp_id>-<frontend>.tar.gz
        Args:
            exp_dir: Where to saves the tar.gz files. If none is provided
            it will save in the current folder.
        """
        if exp_dir is None:
            dest_dir = str(pathlib.Path.cwd())
        else:
            dest_dir = str(pathlib.Path(exp_dir))

        self.client.collect_data_experiment(dest_dir)
        exp_id = self.client.get_job_id()
        # getting sites used in tests
        sites = set()
        for sensor in self.sensors:
            sites.add(sensor.site)
        for host in self.hosts:
            sites.add(host.site)

        user, _ = iotlabcli.auth.get_user_credentials()
        logger.info(
            "Collecting experiment data from sites. Saving in folder: %s", dest_dir
        )
        with play_on(
            roles=[Host(site + ".iot-lab.info", user=user) for site in sites],
            on_error_continue=True,
        ) as p:
            filename = "%d-{{ inventory_hostname }}.tar.gz" % (exp_id)
            # use --ignore-command-error to avoid errors if monitoring
            # files are being written
            p.shell(
                "cd .iot-lab/; tar --ignore-command-error -czf %s %d/"
                % (filename, exp_id)
            )
            p.fetch(src=".iot-lab/" + filename, dest=dest_dir + "/", flat=True)
            p.shell("cd .iot-lab/; rm -f %s" % filename)

    def destroy(self, wait=False):
        """Destroys the job and monitoring profiles."""
        profiles = self.provider_conf.profiles

        if not profiles:
            profiles = []

        self.client.destroy(self.provider_conf.job_name, profiles, wait=wait)

    def reset(self):
        """Reset all sensors."""
        image_dict = {}
        for sensor in self.sensors:
            if sensor.image is not None:
                image_dict.setdefault(sensor.image, []).append(sensor.address)
        for image, sensors in image_dict.items():
            self.client.flash_nodes(image, sensors)

    def _assert_clear_pool(self, pool_nodes):
        """Auxiliary method to verify that all nodes from the pool were used"""
        for nodes in pool_nodes.values():
            assert len(nodes) == 0

    def _populate_from_board_nodes(self, iotlab_nodes: list):
        """Populate self.host from board nodes"""
        pool_nodes = mk_pools(iotlab_nodes, lambda n: (n["site"], n["archi"]))
        for config in self.provider_conf.machines:
            iot_nodes = pick_things(
                pool_nodes, (config.site, config.archi), config.number
            )
            for node in iot_nodes:
                if ssh_enabled(node["network_address"]):
                    iotlab_host = IotlabHost(
                        address=node["network_address"],
                        roles=config.roles,
                        site=node["site"],
                        uid=node["uid"],
                        archi=node["archi"],
                    )
                    self.hosts.append(iotlab_host)
                else:
                    iotlab_sensor = IotlabSensor(
                        address=node["network_address"],
                        roles=config.roles,
                        site=node["site"],
                        uid=node["uid"],
                        archi=node["archi"],
                        image=config.image,
                        iotlab_client=self.client,
                    )
                    self.sensors.append(iotlab_sensor)

        self._assert_clear_pool(pool_nodes)

    def _populate_from_phys_nodes(self, iotlab_nodes: list):
        """Populate self.host from physical nodes"""
        pool_nodes = mk_pools(iotlab_nodes, lambda n: n["network_address"])
        for config in self.provider_conf.machines:
            for s in config.hostname:
                # only 1 is available selecting by hostname
                iot_node = pick_things(pool_nodes, s, 1)[0]
                if ssh_enabled(iot_node["network_address"]):
                    iotlab_host = IotlabHost(
                        address=iot_node["network_address"],
                        roles=config.roles,
                        site=iot_node["site"],
                        uid=iot_node["uid"],
                        archi=iot_node["archi"],
                    )
                    self.hosts.append(iotlab_host)
                else:
                    iotlab_sensor = IotlabSensor(
                        address=iot_node["network_address"],
                        roles=config.roles,
                        site=iot_node["site"],
                        uid=iot_node["uid"],
                        archi=iot_node["archi"],
                        image=config.image,
                        iotlab_client=self.client,
                    )
                    self.sensors.append(iotlab_sensor)

        self._assert_clear_pool(pool_nodes)

    def _deploy(self):
        """
        Deploy image on nodes as described in given configuration

        Wait for A8 nodes to boot
        """
        self.reset()

        self.client.wait_ssh([h.ssh_address for h in self.hosts])

    @staticmethod
    def timezone():
        import pytz

        return pytz.timezone("Europe/Paris")

    def _reserve(self, wait: bool = True):
        """Reserve resources on platform"""
        try:
            self.client.get_or_create_resources(
                self.provider_conf.job_name,
                self.provider_conf.walltime,
                self.provider_conf.machines,
                self.provider_conf.start_time,
            )
        except HTTPError as error:
            # OAR is kind enough to provide an estimate for a possible start time.
            # we capture this start time (if it exists in the error) to forge a special
            # error. This error is used for example in a multi-providers setting
            # to update the search window of the common slot.
            search = re.search(
                r"Reservation not valid --> KO \(This reservation could run at (\d{4}-"
                r"\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)",
                format(error),
            )
            if search is not None:
                date = datetime.strptime(search.group(1), "%Y-%m-%d %H:%M:%S")
                date = self.timezone().localize(date)
                raise InvalidReservationTime(date)
            search = re.search(
                "Reservation too old",
                format(error),
            )
            if search is not None:
                raise InvalidReservationTooOld()
            else:
                raise InvalidReservationCritical(format(error))

        if not wait:
            return

        self.client.wait_experiment()

        # once it's running we can request the exact set of nodes
        iotlab_nodes = self.client.get_nodes()

        if isinstance(self.provider_conf.machines[0], PhysNodeConfiguration):
            self._populate_from_phys_nodes(iotlab_nodes)
        else:
            self._populate_from_board_nodes(iotlab_nodes)

        self._get_networks()

        logger.info(
            "Finished reserving nodes: hosts %s, sensors %s",
            str(self.hosts),
            str(self.sensors),
        )

    def _get_networks(self):
        """
        Get networks used by A8 nodes on platform

        By now use a fixed list of addresses since the API
        doesn't provide any information about networks in testbed.
        """
        networks_info = {
            "grenoble": [
                "10.0.12.0/21",
                "2001:660:5307:3000::/64",
            ],
            "paris": [
                "10.0.68.0/21",
                "2001:660:330f:a200::/64",
            ],
            "saclay": [
                "10.0.44.0/21",
                "2001:660:3207:400::/64",
            ],
            "strasbourg": [
                "10.0.36.0/21",
                "2001:660:4701:f080::/64",
            ],
            "lyon": [
                "10.0.100.0/21",
            ],
        }
        sites = set()
        for host in self.hosts:
            sites.add(host.site)

        # add networks from user
        for net in self.provider_conf.networks:
            self.networks.extend(
                [
                    IotlabNetwork(roles=net.roles, address=addr)
                    for addr in networks_info.get(net.site.lower(), [])
                ]
            )
            sites.discard(net.site.lower())

        # add default networks not in conf
        for site in sites:
            self.networks.extend(
                [
                    IotlabNetwork(roles=[PROD], address=addr)
                    for addr in networks_info.get(site.lower(), [])
                ]
            )

    def _profiles(self):
        """Create profiles"""
        if self.provider_conf.profiles is None:
            return

        for profile in self.provider_conf.profiles:
            if profile.radio is None and profile.consumption is None:
                continue

            self.client.create_profile(
                name=profile.name,
                archi=profile.archi,
                radio=profile.radio,
                consumption=profile.consumption,
            )

    def _to_enoslib(self):
        """Transform from provider specific resources to library-level resources"""
        roles = Roles()
        # keep track of duplicates
        _hosts = []
        for host in self.hosts:
            if host.ssh_address:
                h = Host(host.ssh_address, user="root")
                if h in _hosts:
                    h = _hosts[_hosts.index(h)]
                else:
                    _hosts.append(h)
                roles.add_one(h, host.roles)
                # shouldn't I be able to pass only host?
                # Not because ansible inventory is based on address and
                # our ssh_address is other for A8 nodes.
        for sensor in self.sensors:
            for role in sensor.roles:
                roles[role] += [sensor]

        networks = Networks()
        for network in self.networks:
            networks.add_one(network, network.roles)

        return roles, networks

    def test_slot(self, start_time: int, end_time: int) -> bool:
        """Test if it is possible to reserve the configuration corresponding
        to this provider at start_time"""
        if self.nodes_status is None:
            self.nodes_status = self.client.api.get_nodes()
            from datetime import datetime

            start_param = datetime.fromtimestamp(
                datetime.now().timestamp() + 60, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            stop_param = datetime.fromtimestamp(
                end_time + self.provider_conf.walltime_s, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.experiments_status = self.client.api.method(
                url=f"drawgantt/experiments?start={start_param}&stop={stop_param}"
            )
        return test_slot(
            self.provider_conf, self.nodes_status, self.experiments_status, start_time
        )

    def set_reservation(self, timestamp: int):
        # input timestamp is utc by design
        date = datetime.fromtimestamp(timestamp, timezone.utc)

        import pytz

        tz = pytz.timezone("Europe/Paris")
        date = date.astimezone(tz=tz)
        self.provider_conf.start_time = date.strftime("%Y-%m-%d %H:%M:%S")

    def offset_walltime(self, offset: int):
        walltime_part = self.provider_conf.walltime.split(":")
        walltime_sec = (
            int(walltime_part[0]) * 3600 + int(walltime_part[1]) * 60 + offset
        )
        if walltime_sec <= 0:
            raise NegativeWalltime()
        # The walltime being in Hours:Minutes format, it will be rounded down if
        # there're spare seconds
        new_walltime = time(
            hour=int(walltime_sec / 3600), minute=int((walltime_sec % 3600) / 60)
        )
        self.provider_conf.walltime = new_walltime.strftime("%H:%M")

    def is_created(self):
        return self.client.job_is_active(self.provider_conf.job_name) != (
            None,
            None,
        )
