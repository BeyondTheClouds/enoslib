import re
import sys
import time
from typing import Dict, List, Optional, Tuple, Set
from urllib.error import HTTPError

import iotlabcli
import iotlabcli.experiment
import iotlabcli.node
import iotlabcli.profile
import iotlabsshcli.open_linux
import pytz

from enoslib.infra.enos_iotlab.error import EnosIotlabCfgError

from enoslib.infra.enos_iotlab.constants import (
    PROFILE_POWER_DEFAULT,
)

from enoslib.infra.enos_iotlab.configuration import (
    Configuration,
    GroupConfiguration,
    BoardConfiguration,
    PhysNodeConfiguration,
    RadioConfiguration,
    ConsumptionConfiguration,
)
from enoslib.log import getLogger

logger = getLogger(__name__, ["IOTlab"])


class IotlabAPI:
    """Wrapper for accessing the FIT/IoT-LAB platform through the iotlabcli"""

    def __init__(self):
        user, passwd = iotlabcli.auth.get_user_credentials()
        if user is None:
            raise (
                EnosIotlabCfgError(
                    """Error initializing iotlab client,
            no username/password available. EnOSlib depends on the cli-tools.
            Please create the IoT-LAB password file (~/.iotlabrc) using
            the command 'iotlab-auth -u <username> -p <password>'"""
                )
            )
        self.api = iotlabcli.rest.Api(user, passwd)
        self.user = user
        self.password = passwd

        # this state can be reloaded from the conf
        self.job_id = None
        self.walltime = None
        self.profiles: Set[str] = set()

        # this state depend on the previous ones
        self.nodes = []

    @staticmethod
    def _walltime_to_minutes(walltime: str) -> int:
        """Convert from string format (HH:MM) to minutes"""
        _t = walltime.split(":")
        return int(_t[0]) * 60 + int(_t[1])

    @staticmethod
    def _translate_resources(resources: List[GroupConfiguration]) -> list:
        """Convert from node Configuration to a list of resources of FIT/IoT-LAB

        Args:
            resources: list of resources from schema configuration
        Returns:
            list: list of iotlabcli.experiment.exp_resources
        """
        converted = []
        for cfg in resources:
            if isinstance(cfg, BoardConfiguration):
                converted.append(
                    iotlabcli.experiment.exp_resources(
                        nodes=iotlabcli.experiment.AliasNodes(
                            nbnodes=cfg.number, site=cfg.site, archi=cfg.archi
                        ),
                        profile_name=cfg.profile,
                    )
                )
            elif isinstance(cfg, PhysNodeConfiguration):
                converted.append(
                    iotlabcli.experiment.exp_resources(
                        nodes=cfg.hostname,
                        profile_name=cfg.profile,
                    )
                )
            else:
                sys.exit(
                    """The impossible happened again. Resource: %s is neither
                    a BoardConfiguration neither PhysNodeConfiguration"""
                    % (str(cfg))
                )

        return converted

    def submit_experiment(
        self,
        name: str,
        walltime: str,
        resources: List[GroupConfiguration],
        start_time: str,
    ):
        """
        Submit experiment to FIT/IoT-LAB platform

        Convert parameters to values supported by iotlabcli library

        Args:
            name: Job name
            walltime: Job walltime in HH:MM format
            resources: List of nodes in job
            start_time: Time at which you precisely wish to start the job,
                by default None (meaning now)
        """
        converted = self._translate_resources(resources)
        logger.info(
            (
                "Submitting FIT/IoT-LAB: "
                " job id: %s, "
                "start_time=%s, "
                "duration: %s, "
                "resources: %s"
            ),
            name,
            start_time,
            walltime,
            str(converted),
        )

        from datetime import datetime

        start_time_timestamp = None
        if start_time:
            timezone = pytz.timezone("Europe/Paris")
            start_time_timestamp = str(
                int(
                    timezone.localize(
                        datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    ).timestamp()
                )
            )

        json_res = iotlabcli.experiment.submit_experiment(
            api=self.api,
            name=name,
            duration=self._walltime_to_minutes(walltime),
            resources=converted,
            start_time=start_time_timestamp,
        )
        # urllib.error.HTTPError: HTTP Error 500:
        # {"code":500,"message":"Invalid nodes state : [m3-1.grenoble.iot-lab.info]"}
        # OK: {'id': 237179}
        self.job_id = json_res["id"]
        self.walltime = self._walltime_to_minutes(walltime)
        logger.info("Job submitted: %d", self.job_id)

    def reload_resources(self, name: str):
        # reload the job
        self.job_id, self.walltime = self.job_is_active(name)

    def reload_profiles(self, profiles_conf):
        # reload the profiles
        self.profiles = set()
        for profile_conf in profiles_conf:
            if self._check_profile_exists(profile_conf.name):
                self.profiles.add(profile_conf.name)

    def destroy(self, name: str, profiles_conf, wait=False):
        self.reload_resources(name)
        self.stop_experiment()

        self.reload_profiles(profiles_conf)
        self.del_profiles()

        while wait and self.job_is_active(name) != (None, None):
            time.sleep(3)

    def job_is_active(self, name: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Check if job is already running

        Args:
            name: Job name
        Returns:
            int, int: (job identifier, walltime) or (None, None) if not found
        """
        act_jobs = iotlabcli.experiment.get_experiments_list(
            self.api, state=",".join(iotlabcli.helpers.ACTIVE_STATES), limit=0, offset=0
        )
        # output example: { 'items': [{'id': 237466, 'name': 'EnOSlib',
        # 'user': 'donassol', 'state': 'Running',
        # 'submission_date': '2020-11-30T09:58:28Z',
        # 'start_date': '2020-11-30T09:58:30Z', 'stop_date': '1970-01-01T00:00:00Z',
        # 'effective_duration': 10, 'submitted_duration': 120, 'nb_nodes': 1,
        # 'scheduled_date': '2020-11-30T09:58:30Z'}]}

        for job in act_jobs["items"]:
            if job["name"] == name:
                return job["id"], job["submitted_duration"]

        return None, None

    def healthcheck(self):
        """Used to check connectivity to the API."""
        iotlabcli.experiment.get_experiments_list(
            self.api, state=",".join(iotlabcli.helpers.ACTIVE_STATES), limit=0, offset=0
        )

    def get_or_create_resources(
        self,
        name: str,
        walltime: str,
        resources: List[GroupConfiguration],
        start_time: str,
    ):
        """
        Get resources from FIT/IoT-LAB platform

        Submit "name" job with (if not already running in platform),
        wait for it to be running and return list of resources

        Args:
            name: Job name
            walltime: Job walltime in HH:MM format
            resources: List of nodes in job
            start_time: Time at which you precisely wish to start the job,
            by default None
        Returns:
            list: List with nodes name
        """
        self.reload_resources(name)
        if self.job_id is None:
            self.submit_experiment(name, walltime, resources, start_time)

    def get_nodes(self):
        job_info = iotlabcli.experiment.get_experiment(
            api=self.api, exp_id=self.job_id, option="nodes"
        )
        # output example: {'items': [{'site': 'grenoble', 'archi': 'a8:at86rf231',
        # 'uid': 'b564', 'x': '20.33', 'state': 'Alive',
        # 'network_address': 'a8-1.grenoble.iot-lab.info', 'z': '2.63',
        # 'production': 'YES', 'y': '25.28', 'mobile': '0',
        # 'mobility_type': ' ', 'camera': None}]}

        self.nodes = job_info["items"]
        return self.nodes

    def wait_experiment(self):
        if self.job_id:
            logger.info("Waiting for job id (%d) to be in running state", self.job_id)
            iotlabcli.experiment.wait_experiment(api=self.api, exp_id=self.job_id)
            logger.info("Job id (%d) is running", self.job_id)
        else:
            raise ValueError("Can't wait on an experiment that hasn't been submitted")

    def stop_experiment(self):
        """Stop experiment if it's active"""
        if self.job_id:
            logger.info("Stopping experiment id (%d)", self.job_id)
            try:
                iotlabcli.experiment.stop_experiment(api=self.api, exp_id=self.job_id)
            except HTTPError as error:
                search = re.search(
                    "This job was already killed",
                    format(error),
                )
                if search is None:
                    raise error

    def collect_data_experiment(self, exp_dir: str):
        """
        Collect tar.gz with data about experiment

        Args:
            exp_dir: Where to save the tar.gz file
        """
        if self.job_id is None:
            return

        logger.info("API exp info saved in %s/%d.tar.gz file.", exp_dir, self.job_id)
        result = self.api.get_experiment_info(expid=self.job_id, option="data")
        with open(f"{exp_dir}/{self.job_id}.tar.gz", "wb") as archive:
            archive.write(result)

    def flash_nodes(self, image: str, nodes: List[str]):
        """
        Flash image in sensor nodes

        Args:
            image: Image filename
            nodes: List of nodes to flash image
        """

        logger.info("Flashing image (%s) on nodes (%s)", image, str(nodes))
        iotlabcli.node.node_command(
            api=self.api,
            command="flash",
            exp_id=self.job_id,
            nodes_list=nodes,
            cmd_opt=image,
        )

    def wait_ssh(self, nodes: List[str]):
        """
        Wait A8 nodes to boot

        A8 nodes can take some time to boot and to be accessible through ssh.
        Use this command to wait them to boot.

        Args:
            nodes: list of nodes (ssh_address in the format node-a8...)
        """

        if len(nodes) == 0:
            return
        logger.info("Waiting nodes to boot: %s", str(nodes))
        res = iotlabsshcli.open_linux.wait_for_boot(
            {"user": self.user, "exp_id": self.job_id}, nodes
        )
        # handling errors
        if "1" in res["wait-for-boot"] and len(res["wait-for-boot"]["1"]) > 0:
            msg = (
                """
Error initializing nodes: %s. \
Try to restart them in frontend using 'iotlab-node' command \
or choose other nodes"""
                % res["wait-for-boot"]["1"]
            )
            logger.error(msg)

        if "0" in res["wait-for-boot"] and len(res["wait-for-boot"]["0"]) > 0:
            logger.info("Nodes initialized: %s", res["wait-for-boot"]["0"])

    def send_cmd_node(self, cmd: str, nodes: List[str]):
        """
        Send command to nodes

        Acceptable commands: start, stop, reset.

        Args:
            cmd: Command (start, stop, reset)
            nodes: List of nodes
        """
        acceptable = ["start", "stop", "reset"]
        if cmd not in acceptable:
            sys.exit(f"Invalid command: {cmd}, nodes: {str(nodes)}")

        logger.info("Executing command (%s) on nodes (%s)", cmd, str(nodes))
        iotlabcli.node.node_command(
            api=self.api, command=cmd, exp_id=self.job_id, nodes_list=nodes
        )

    def get_job_id(self) -> int:
        """Get experiment ID"""
        return self.job_id

    def get_walltime(self) -> int:
        """Get experiment walltime"""
        return self.walltime

    def create_profile(
        self,
        name: str,
        archi: str,
        radio: Optional[RadioConfiguration],
        consumption: Optional[ConsumptionConfiguration],
    ):
        """
        Create monitoring profiles on testbed

        FIT/IoT-LAB provides the monitoring of radio properties (rssi, sniffer)
        and consumption (power, voltage, etc), this method creates the monitoring
        profiles on the testbed.

        Args:
            name: Profile name to be created
            archi: Target architecture (M3, A8, custom)
            radio: Profile for radio monitoring
            consumption: Profile for consumption monitoring
        """
        profile_class_dict = {
            "a8": iotlabcli.profile.ProfileA8,
            "m3": iotlabcli.profile.ProfileM3,
            "custom": iotlabcli.profile.ProfileCustom,
        }

        if self._check_profile_exists(name):
            logger.info("Profile: %s, already exists. Skipping creation.", name)
            self.profiles.add(name)
            return

        profile = profile_class_dict[archi](
            profilename=name, power=PROFILE_POWER_DEFAULT
        )
        if radio is not None:
            profile.set_radio(
                mode=radio.mode,
                channels=radio.channels,
                period=radio.period,
                num_per_channel=radio.num_per_channel,
            )

        if consumption is not None:
            profile.set_consumption(
                period=consumption.period,
                average=consumption.average,
                power=consumption.power,
                voltage=consumption.voltage,
                current=consumption.current,
            )

        res = self.api.add_profile(profile)
        logger.info("Submitting profile: %s, got %s", name, str(res))
        self.profiles.add(name)
        return

    def del_profiles(self):
        """Deletes the profiles from testbed"""
        for profile in self.profiles:
            logger.info("Deleting monitoring profile: %s", profile)
            self.api.del_profile(name=profile)
        self.profiles.clear()
        return

    def _check_profile_exists(self, name: str) -> bool:
        """
        Verify if a profile with the same name already
        exists in the testbed

        Args:
            name: Profile name to be created
        Returns:
            bool: True if profile already exists, false otherwise
        """

        profiles = self.api.get_profiles()
        # [
        #    {
        #        "nodearch": "m3",
        #        "power": "dc",
        #        "profilename": "test_profile",
        #        "radio": {
        #            "channels": [
        #                11,
        #                14
        #            ],
        #            "mode": "rssi",
        #            "num_per_channel": 1,
        #            "period": 1
        #        }
        #    }
        # ]

        for p in profiles:
            if p["profilename"] == name:
                return True

        return False


def get_candidates(nodes_status: Dict) -> Dict:
    """
    Takes a dictionary with the status of all the nodes as returned by the api and
    returns the functioning ones (Alive or Busy) indexed by their network_address(fqn)
    """
    candidates = {}
    nodes = nodes_status.get("items")
    for node_status in nodes:
        if node_status["state"] == "Alive" or node_status["state"] == "Busy":
            candidates[node_status["network_address"]] = node_status
    return candidates


def get_free_nodes(
    candidates: Dict, experiments_status: Dict, start: int, walltime: int
) -> Dict:
    """
    Takes a dictionary with all functioning nodes, all experiments status,
    a start timestamp and a walltime and return all free nodes on that period of time

    Args:
        candidates: All functioning nodes in a dictionary
        experiments_status: All experiments and their status in a dictionary
        start: start timestamp
        walltime: length required

    Returns:
        free node indexed by their network_address(fqdn)

    """
    experiments = experiments_status.get("items")
    from datetime import datetime
    import copy

    # at start every node is considered as free
    # and we'll remove from them the nodes with conflicting reservation
    copy_candidates = copy.deepcopy(candidates)
    for experiment_status in experiments:
        timezone = pytz.timezone("UTC")
        experiment_start_date = timezone.localize(
            datetime.strptime(experiment_status["start_date"], "%Y-%m-%dT%H:%M:%SZ")
        ).timestamp()
        # submitted duration is given in minutes !
        exp_end_date = experiment_start_date + int(
            experiment_status["submitted_duration"] * 60
        )
        if start >= exp_end_date:
            continue
        if start + walltime <= experiment_start_date:
            continue
        # intersection remove all the nodes of the xp from the candidates
        for node in experiment_status["nodes"]:
            if node in copy_candidates:
                copy_candidates.pop(node)
    return copy_candidates


def test_slot(
    conf: Configuration, nodes_status: Dict, experiments_status: Dict, start_time: int
) -> bool:
    """
    Check if it is possible to start nodes requested by conf at time start_time
    This is intended to give a good enough approximation.
    This can be used to prefilter possible reservation dates before submitting
    them on oar.

    Args:
        conf: an iotlab configuration object
        nodes_status: a dictionary with all the status of the nodes as
            returned by the api
        experiments_status: a dictionary with all the status of the experiments
            as returned by the api
        start_time: start time of the job to test

    Returns:
        True iff the slot is free and thus can be reserved
    """
    machines_required = {}
    candidates = get_candidates(nodes_status)
    walltime = conf.walltime_s
    logger.debug(f"Test slot: start_time={start_time}, walltime={walltime}")

    free_nodes = get_free_nodes(candidates, experiments_status, start_time, walltime)
    for machines in conf.machines:
        if isinstance(machines, BoardConfiguration):
            machines_required.setdefault((machines.archi, machines.site), 0)
            machines_required[(machines.archi, machines.site)] = (
                machines_required[(machines.archi, machines.site)] + machines.number
            )
        else:
            if not set(machines.hostname).issubset([f for f in free_nodes]):
                return False
            # machines share the same architecture within a group
            archi = free_nodes[machines.hostname[0]]["archi"]
            site = free_nodes[machines.hostname[0]]["site"]
            machines_required.setdefault((archi, site), 0)
            machines_required[(archi, site)] = machines_required[(archi, site)] + len(
                machines.hostname
            )
    for (archi, site), number in machines_required.items():
        availables = [
            f
            for f in free_nodes
            if free_nodes[f]["archi"] == archi and free_nodes[f]["site"] == site
        ]
        available = len(availables)
        if available < number:
            return False
    return True
