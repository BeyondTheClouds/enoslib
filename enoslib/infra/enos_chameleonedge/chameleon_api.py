import time
from typing import List, Set
import logging
import zunclient.v1.containers
from chi import lease
from chi import container
from zunclient.v1.containers import Container
from enoslib.infra.enos_chameleonedge.configuration import (
    DeviceGroupConfiguration,
    DeviceClusterConfiguration,
    DeviceConfiguration,
)
from .chi_api_utils import (
    source_credentials_from_rc_file,
    wait_for_addresses,
)
from .constants import (
    ROLES,
    ROLES_SEPARATOR,
    CONTAINER_LABELS,
    CONTAINER_STATUS,
    LEASE_ID,
)

logger = logging.getLogger(__name__)


class ChameleonAPI:
    """Wrapper for accessing the Chameleon platform through the python-chi"""

    def __init__(self):
        self.lease_id = None
        self.walltime = None
        self.profiles: Set[str] = set()
        self.concrete_resources = []

    def get_resources(
        self,
        lease_name: str,
        walltime: str,
        rc_file: str,
        resources: List[DeviceGroupConfiguration],
    ):
        """Get resources from Chameleon platform.

        Convert from node Configuration to resources acceptable by Chameleon.
        Convert parameters to values supported by python-chi library.

        Args:
            lease_name: Lease name
            walltime: Job walltime in HH:MM format
            rc_file: OpenRC file
            resources: List of nodes in job

        Returns:
            dict: The lease representation
        """
        with source_credentials_from_rc_file(rc_file) as _site:
            _lease = ChameleonAPI._get_lease(lease_name)
            if _lease is not None:
                if ChameleonAPI.lease_is_reusable(_lease):
                    logger.info(f"Reusing lease: {_lease['name']}/{_lease['id']}")
                else:
                    logger.warning(
                        f"Lease is OVER, destroying lease: "
                        f"{_lease['name']}/{_lease['id']}"
                    )
                    ChameleonAPI._delete_lease(_lease["name"])
                    _lease = ChameleonAPI._create_lease(resources, lease_name, walltime)
            else:
                _lease = ChameleonAPI._create_lease(resources, lease_name, walltime)
            ChameleonAPI._lease_wait_for_active(_lease, _site)
        return _lease

    def deploy_containers(
        self,
        rc_file: str,
        resources: List[DeviceGroupConfiguration],
        leased_resources: dict,
    ) -> List[Container]:
        with source_credentials_from_rc_file(rc_file) as _site:
            self.concrete_resources = ChameleonAPI.get_containers_by_lease_id(
                leased_resources["id"]
            )
            if self.concrete_resources:
                logger.info(f" Getting existing containers: {self.concrete_resources}.")
            else:
                logger.info("Creating new containers.")
                self._create_container_from_config(resources, leased_resources)

            logger.info(f"[{_site}]: Waiting for resources to be ready...")
            for concrete_resource in self.concrete_resources:
                if isinstance(concrete_resource, Container):
                    logger.info(
                        container.wait_for_active(concrete_resource.uuid).status
                    )
                    wait_for_addresses(concrete_resource.uuid)
        return self.concrete_resources

    @staticmethod
    def get_container(container_ref):
        return container.get_container(container_ref)

    @staticmethod
    def get_containers_by_lease_id(lease_id: str):
        filtered_containers = []
        for _container in container.list_containers():
            # filter containers by status: "Running" or "Creating"
            if _container.status not in CONTAINER_STATUS:
                continue
            # filter containers by lease id
            if (
                hasattr(_container, CONTAINER_LABELS)
                and LEASE_ID in _container.__getattr__(CONTAINER_LABELS)
                and _container.__getattr__(CONTAINER_LABELS)[LEASE_ID] == lease_id
            ):
                filtered_containers.append(_container)
        return filtered_containers

    @staticmethod
    def lease_is_reusable(_lease):
        statuses = ["CREATING", "STARTING, UPDATING", "ACTIVE", "PENDING"]
        return _lease["status"] in statuses

    @staticmethod
    def _get_lease(lease_name):
        try:
            return lease.get_lease(lease_name)
        except Exception as e:
            logger.warning(e)
            return None

    @staticmethod
    def _create_lease(resources, lease_name, walltime):
        logger.info("Creating a new lease!")
        reservations: List[dict] = []
        for cfg in resources:
            if isinstance(cfg, DeviceClusterConfiguration):
                lease.add_device_reservation(
                    reservations, count=cfg.count, machine_name=cfg.machine_name
                )
            elif isinstance(cfg, DeviceConfiguration):
                lease.add_device_reservation(
                    reservations, count=1, device_name=cfg.device_name
                )
            else:
                raise ValueError(
                    f"Resource: {cfg} is not a ClusterConfiguration "
                    f"neither a DevicesConfiguration"
                )
        logger.info(
            " Submitting Chameleon: lease name: %s, " "duration: %s, resources: %s",
            lease_name,
            walltime,
            str(reservations),
        )

        return ChameleonAPI._try_create_lease(
            lease_name,
            reservations,
            walltime,
        )

    @staticmethod
    def _try_create_lease(lease_name, reservations, walltime):
        start_date, end_date = ChameleonAPI._get_lease_start_end_duration(walltime)
        retry_time = 60
        while True:
            try:
                return lease.create_lease(
                    lease_name,
                    reservations=reservations,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception:
                logger.info(f"Retrying to create lease every {retry_time} secs...")
                time.sleep(retry_time)
                start_date, end_date = ChameleonAPI._get_lease_start_end_duration(
                    walltime
                )

    @staticmethod
    def _get_lease_start_end_duration(walltime):
        return lease.lease_duration(
            days=0, hours=ChameleonAPI._walltime_to_hours(walltime)
        )

    @staticmethod
    def _lease_wait_for_active(leased_resources, _site):
        lease_id = leased_resources["id"]
        logger.info(
            f"[{_site}]:wait for the lease " f"[lease_id={lease_id}] to be active..."
        )
        retry_time = 10
        while True:
            try:
                lease.wait_for_active(lease_id)
                logger.info("Lease id (%s) is active!", lease_id)
                break
            except Exception as e:
                logger.error(e)
                logger.info(f"Retrying every {retry_time} secs...")
                time.sleep(retry_time)

    def _create_container_from_config(self, resources, leased_resources):
        for cfg in resources:
            if isinstance(cfg, DeviceClusterConfiguration):
                self._create_container(
                    leased_resources, "$machine_name", cfg.machine_name, cfg
                )
            elif isinstance(cfg, DeviceConfiguration):
                self._create_container(leased_resources, "$name", cfg.device_name, cfg)

    def _create_container(self, leased_resources, _group, _name, cfg):
        reservation_id = lease.get_device_reservation(
            lease_ref=leased_resources["id"],
            count=cfg.count,
            machine_name=_name if _group in ["$machine_name"] else None,
            device_model=cfg.device_model,
            device_name=_name if _group in ["$name"] else None,
        )
        for node in range(cfg.count):
            self.concrete_resources.append(
                container.create_container(
                    name=f"{cfg.container.name}-{node + 1}",
                    image=cfg.container.image,
                    exposed_ports=cfg.container.exposed_ports,
                    reservation_id=reservation_id,
                    start=cfg.container.start,
                    start_timeout=cfg.container.start_timeout,
                    **self.get_container_kwargs(cfg, leased_resources["id"]),
                )
            )

    @staticmethod
    def release_resources(lease_name: str, rc_file: str):
        with source_credentials_from_rc_file(rc_file):
            ChameleonAPI._delete_lease(lease_name)

    @staticmethod
    def _delete_containers(lease_name: str):
        _lease = ChameleonAPI._get_lease(lease_name)
        if _lease:
            logger.info("Deleting containers...")
            for _container in ChameleonAPI.get_containers_by_lease_id(_lease["id"]):
                container.destroy_container(_container.uuid)
                logger.info(f"Container {_container.uuid} deleted!")

    @staticmethod
    def _delete_lease(lease_name: str):
        if ChameleonAPI._get_lease(lease_name):
            logger.info("Deleting lease...")
            lease.delete_lease(lease_name)

    @staticmethod
    def get_container_kwargs(cfg, lease_id: str):
        kwargs = zunclient.v1.containers.CREATION_ATTRIBUTES.copy()
        for attr in ["name", "image", "exposed_ports", CONTAINER_LABELS]:
            kwargs.remove(attr) if attr in kwargs else None
        extra_attr = {
            "interactive": True,
            CONTAINER_LABELS: {
                ROLES: ChameleonAPI.add_roles_in_container(cfg.roles),
                LEASE_ID: lease_id,
            },
        }
        for kwarg in kwargs:
            if kwarg in cfg.container.kwargs:
                extra_attr[kwarg] = cfg.container.kwargs[kwarg]
        return extra_attr

    @staticmethod
    def add_roles_in_container(roles):
        return ROLES_SEPARATOR.join(roles)

    @staticmethod
    def execute(uuid: str, rc_file: str, command: str):
        with source_credentials_from_rc_file(rc_file):
            result = container.execute(uuid, command)
        return result

    @staticmethod
    def upload(uuid: str, rc_file: str, source: str, dest: str):
        with source_credentials_from_rc_file(rc_file):
            result = container.upload(uuid, source, dest)
        return result

    @staticmethod
    def download(uuid: str, rc_file: str, source: str, dest: str):
        with source_credentials_from_rc_file(rc_file):
            # This chi API currently returns None, but it could change in
            # the future.
            # pylint: disable-next=assignment-from-no-return
            result = container.download(uuid, source, dest)
        return result

    @staticmethod
    def associate_floating_ip(uuid: str, rc_file: str):
        with source_credentials_from_rc_file(rc_file):
            result = container.associate_floating_ip(uuid)
        return result

    @staticmethod
    def destroy_container(uuid: str, rc_file: str):
        with source_credentials_from_rc_file(rc_file):
            result = container.destroy_container(uuid)
        return result

    @staticmethod
    def get_logs(uuid: str, rc_file: str, stdout: bool = True, stderr: bool = True):
        with source_credentials_from_rc_file(rc_file):
            result = container.get_logs(uuid, stdout, stderr)
        return result

    @staticmethod
    def snapshot_container(
        uuid: str, rc_file: str, repository: str, tag: str = "latest"
    ):
        with source_credentials_from_rc_file(rc_file):
            result = container.snapshot_container(uuid, repository, tag)
        return result

    @staticmethod
    def _walltime_to_hours(walltime: str) -> int:
        """Convert from string format (HH:MM) to hours"""
        _t = walltime.split(":")
        return int(_t[0]) + 1 if int(_t[1]) > 0 else int(_t[0])
