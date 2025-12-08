"""FABRIC provider for EnOSlib.
The provider is used to deploy and manage resources on the FABRIC testbed using the
FABRIC API. The provider will create and manage slices, nodes, and networks.
"""

from __future__ import annotations

# import random
# import string
# from itertools import chain
import base64
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from ipaddress import IPv4Network, IPv6Interface, IPv6Network, ip_interface
from pathlib import Path
from typing import Any, Generator, Union

from fabrictestbed_extensions.fablib.component import Component
from fabrictestbed_extensions.fablib.constants import Constants
from fabrictestbed_extensions.fablib.fablib import FablibManager
from fabrictestbed_extensions.fablib.interface import Interface
from fabrictestbed_extensions.fablib.network_service import NetworkService
from fabrictestbed_extensions.fablib.node import Node
from fabrictestbed_extensions.fablib.slice import Slice

from enoslib.infra.enos_fabric.utils import source_credentials_from_rc_file
from enoslib.infra.provider import Provider
from enoslib.objects import DefaultNetwork, Host, Networks, Roles

from .configuration import (
    Fabnetv4ExternalNetworkConfiguration,
    Fabnetv4NetworkConfiguration,
    Fabnetv6ExternalNetworkConfiguration,
    Fabnetv6NetworkConfiguration,
    L2BridgeNetworkConfiguration,
    L2SiteToSiteNetworkConfiguration,
    MachineConfiguration,
)
from .constants import (
    FABNETV4EXT,
    FABNETV6EXT,
    GPU,
    L2BRIDGE,
    L2STS,
    NIC,
    NIC_BASIC,
    NIC_MODEL_CONNECTX_5,
    NIC_MODEL_CONNECTX_6,
    NIC_SHARED,
    NIC_SMART,
    NVME,
    PERMISSION_CONNECTX_5,
    PERMISSION_CONNECTX_6,
    PERMISSION_FABNETV4_EXT,
    PERMISSION_FABNETV6_EXT,
    PERMISSION_GPU,
    PERMISSION_NVME,
    PERMISSION_NVME_P4510,
    PERMISSION_SLICE_MULTISITE,
    PERMISSION_STORAGE,
    STORAGE,
    STORAGE_MODEL_P4510,
)

logger = logging.getLogger(__name__)

NetworkConfigTypes = Union[
    Fabnetv4NetworkConfiguration,
    Fabnetv6NetworkConfiguration,
    Fabnetv4ExternalNetworkConfiguration,
    Fabnetv6ExternalNetworkConfiguration,
    L2BridgeNetworkConfiguration,
    L2SiteToSiteNetworkConfiguration,
]


class FabricNetwork(DefaultNetwork):
    def __init__(
        self,
        config: NetworkConfigTypes,
        gateway=None,
        dns=None,
        ip_start=None,
        ip_end=None,
        mac_start=None,
        mac_end=None,
    ):
        self.config: NetworkConfigTypes = config
        super().__init__(
            config.network, gateway, dns, ip_start, ip_end, mac_start, mac_end
        )

    @property  # type: ignore[override]
    def network(self) -> IPv4Network | IPv6Network | frozenset[IPv6Interface]:
        if isinstance(
            self.config,
            (Fabnetv6NetworkConfiguration, Fabnetv6ExternalNetworkConfiguration),
        ):
            return frozenset(self.config._allocated_ips)
        return self._network

    @network.setter
    def network(self, value: IPv4Network | IPv6Network | str):
        self._network = ip_interface(value).network


class Fabric(Provider):
    """The provider to use when working with FABRIC."""

    def __init__(self, provider_conf, name: str | None = None):
        super().__init__(provider_conf, name)
        self.has_public_ip: bool = False
        self.has_storage: bool = False
        self.fablib: FablibManager = None
        self.project_name: str | None = None
        self.project_uuid: str | None = None
        self.permissions: set[str] = set()
        self.slice: Slice = None
        self.nodes: dict[str, Node] = {}
        self.sites: set[str] = set()
        self.networks: dict[str, NetworkService] = {}
        self.provider_conf = self.provider_conf.finalize()

    def init(
        self, force_deploy: bool = False, start_time: int | None = None, **kwargs
    ) -> tuple[Roles, Networks]:
        """Reserve and deploys the FABRIC slices.

        Args:
            force_deploy (bool): True iff new machines should be started
        """
        with source_credentials_from_rc_file(self.provider_conf.rc_file):
            self.fablib = FablibManager(log_propagate=True)
            self.load_id_token()
            self.private_key = os.environ[Constants.FABRIC_SLICE_PRIVATE_KEY_FILE]
            self.gateway_user = os.environ[Constants.FABRIC_BASTION_USERNAME]
            self.gateway = os.environ[Constants.FABRIC_BASTION_HOST]
            self.gateway_private_key = os.environ[Constants.FABRIC_BASTION_KEY_LOCATION]
            self.scripts_dir = Path(__file__).parent / "scripts"

        # Check configuration for checks that can't be done with JSON Schema
        self.check()

        w = self.provider_conf.walltime.split(":")
        lease_in_hours = int(w[0])
        minutes = int(w[1])
        seconds = int(w[2] if len(w) == 2 else 0)

        if minutes > 0 or seconds > 0:
            lease_in_hours += 1

        logger.debug("Creating slice")
        slice_exists = self.create_slice(force_deploy=force_deploy)

        if slice_exists is False:
            logger.debug("Creating nodes")
            self.create_nodes()

            logger.debug("Creating FABRIC networks")
            self.create_fabric_networks()

            logger.debug("Add interfaces to networks")
            self.add_interfaces_to_network()

            try:
                if self.has_storage is False:
                    result = self.slice.validate(raise_exception=False)
                    if result[1]:
                        raise Exception("Validation failed", result[1])

                lease_start_time = (
                    datetime.fromtimestamp(start_time, tz=timezone.utc)
                    if start_time
                    else None
                )
                self.slice.submit(
                    lease_start_time=lease_start_time,
                    lease_in_hours=lease_in_hours,
                    validate=False,
                )

                # Refresh nodes and networks after slice submission
                self.refresh()

                # Configure storage
                self.configure_storage()
            except Exception:
                logger.exception("Error during slice creation")
                raise

            if self.has_public_ip:
                logger.debug("Assigning public IP and making it publicly routable")
                self.assign_public_ip()
                self.slice.submit(validate=False)

                # Refresh nodes and networks after slice submission
                self.refresh()

            logger.debug("Configure network interfaces")
            self.configure_network_interfaces()

        else:
            logger.info("Slice already exists, set the force flag to recreate it")

        roles = self.create_roles()
        networks = self.create_networks()

        logger.debug(roles)
        logger.debug(networks)

        return roles, networks

    def create_slice(self, force_deploy: bool = False) -> bool:
        """Create a new slice or reuse an existing one."""
        try:
            self.slice = self.fablib.get_slice(name=self.provider_conf.name_prefix)
            logger.debug("Slice <%s> exists", self.provider_conf.name_prefix)
            slice_exists = not force_deploy
            if force_deploy is True:
                logger.debug(
                    "Force is true, deleting slice <%s> and creating a new one",
                    self.provider_conf.name_prefix,
                )
                self.slice.delete()
                self.slice = self.fablib.new_slice(name=self.provider_conf.name_prefix)
            else:
                self.refresh()
        except Exception:
            logger.debug(
                "Slice <%s> does not exist, creating a new one",
                self.provider_conf.name_prefix,
            )
            self.slice = self.fablib.new_slice(name=self.provider_conf.name_prefix)
            slice_exists = False

        return slice_exists

    def create_nodes(self) -> None:
        """Create nodes to provision based on the defined machines.

        If a node does not exist, it will be created.
        If a node already exists, it will be reused.
        If a node is no longer needed, it will be deleted.
        """
        slice = self.slice
        sites = self.sites = set()
        nodes = self.nodes
        # existing_nodes = {n.get_name() for n in slice.get_nodes()}
        # config_nodes = set()

        for index_i, index_j, machine in self.itermachines():
            kwargs = {}
            site = kwargs["site"] = machine.site
            name = f"{self.provider_conf.name_prefix}-s{site}-m{index_i}-n{index_j}"
            sites.add(site)
            # config_nodes.add(name)
            node = nodes.get(name)
            if node is None:
                self._submit = True
                has_storage: bool = any([s.kind == STORAGE for s in machine.storage])
                if machine.flavour:
                    kwargs["cores"] = machine.flavour_desc["core"]
                    kwargs["ram"] = machine.flavour_desc["mem"]
                if machine.flavour_desc:
                    kwargs["cores"] = machine.flavour_desc["core"]
                    kwargs["ram"] = machine.flavour_desc["mem"]
                    if "disk" in machine.flavour_desc:
                        kwargs["disk"] = machine.flavour_desc["disk"]
                nodes[name] = node = slice.add_node(
                    name=name,
                    image=machine.image,
                    # TODO(mayani): FABRIC API's validation is buggy,
                    # so skip if storage is present, until it is fixed
                    validate=has_storage is False,
                    raise_exception=True,
                    **kwargs,
                )

            components = {c.get_name(): c for c in node.get_components()}

            # Add GPUs
            self._add_gpus(node, machine, components)

            # Add NVMEs
            self._add_nvme(node, machine, components)

            # Add Storage NAS
            self._add_nas(node, machine, components)

    def _add_gpus(
        self,
        node: Node,
        machine: MachineConfiguration,
        components: dict[str, Component],
    ):
        """Add or remove GPUs to the node.

        If a GPU is not present, it will be added.
        If a GPU is already present, it will be reused.
        If a GPU is no longer needed, it will be deleted.

        :param node: node to add the GPUs to
        :type node: Node
        :param machine: machine configuration
        :type machine: MachineConfiguration
        :param components: components that already exist on the node
        :type components: dict[str, Component]
        """
        # https://fabric-fablib.readthedocs.io/en/latest/node.html#fabrictestbed_extensions.fablib.node.Node.add_component
        # GPU_TeslaT4: Tesla T4 GPU
        # GPU_RTX6000: RTX6000 GPU
        # GPU_A30: A30 GPU
        # GPU_A40: A40 GPU
        name = node.get_name()
        gpu_counter = Counter([f"{GPU}_{c.model}" for c in machine.gpus])
        for model, count in gpu_counter.items():
            for index in range(count):
                gpu_name = f"{model}-{index}"
                logger.debug(
                    "Adding GPU <%s> with name <%s> to node <%s>",
                    model,
                    gpu_name,
                    name,
                )
                node.add_component(model, gpu_name)

    def _add_nvme(
        self,
        node: Node,
        machine: MachineConfiguration,
        components: dict[str, Component],
    ):
        """Add or remove NVMEs to the node.

        If an NVME is not present, it will be added.
        If an NVME is already present, it will be reused.
        If an GPU is no longer needed, it will be deleted.

        :param node: node to add the NVMEs to
        :type node: Node
        :param machine: machine configuration
        :type machine: MachineConfiguration
        :param components: components that already exist on the node
        :type components: dict[str, Component]
        """
        name = node.get_name()
        nvme_counter = Counter(
            [f"{NVME}_{c.model}" for c in machine.storage if c.kind == NVME]
        )
        for model, count in nvme_counter.items():
            for index in range(count):
                nvme_name = f"{model}-{index}"
                logger.debug(
                    "Adding NVME <%s> with name <%s> to node <%s>",
                    model,
                    nvme_name,
                    name,
                )
                node.add_component(model, nvme_name)

    def _add_nas(
        self,
        node: Node,
        machine: MachineConfiguration,
        components: dict[str, Component],
    ):
        """Add or remove NAS storage to the node.

        If a NAS storage is not present, it will be added.
        If a NAS storage is already present, it will be reused.
        If a NAS is no longer needed, it will be deleted.

        :param node: node to add the NAS storage to
        :type node: Node
        :param machine: machine configuration
        :type machine: MachineConfiguration
        :param components: components that already exist on the node
        :type components: dict[str, Component]
        """
        name = node.get_name()
        nas_names = {c.name: c for c in machine.storage if c.kind == STORAGE}
        for storage_name in nas_names:
            self.has_storage = True
            storage = nas_names[storage_name]
            model = f"{storage.kind}_{storage.model}"
            logger.debug(
                "Adding Storage <%s> with name <%s> with auto_mount <%s> to node <%s>",
                model,
                storage.name,
                storage.auto_mount,
                name,
            )
            node.add_storage(storage.name, auto_mount=storage.auto_mount)

    def create_fabric_networks(self) -> None:
        """Create the networks based on the defined networks.

        If a network does not exist, it will be created.
        If a network already exists, it will be reused.
        If a network is no longer needed, it will be deleted.

        :raises NotImplementedError: _description_
        """
        slice = self.slice
        networks = self.networks

        for _index, kind, name, network in self.iternetworks():
            if kind.startswith("L2"):
                if kind == L2BRIDGE:
                    logger.debug(
                        "Creating L2Bridge network <%s> on site <%s>",
                        name,
                        network.site,
                    )
                    networks[name] = slice.add_l2network(name=name, type=kind)
                elif kind == L2STS:
                    if name in networks:
                        continue
                    logger.debug(
                        "Creating L2STS network on <%s> on site <%s>-<%s>",
                        name,
                        network.site_1,
                        network.site_2,
                    )
                    networks[name] = slice.add_l2network(name=name, type=kind)
                else:
                    raise NotImplementedError(f"Unknown L2 network kind {kind}")
            else:
                type = f"IPv{network.ip_version}{'Ext' if 'Ext' in kind else ''}"
                logger.debug("Creating L3Network <%s> with type <%s>", name, type)
                networks[name] = slice.add_l3network(name=name, type=type)
                if "Ext" in kind:
                    self.has_public_ip = True

    def add_interfaces_to_network(self) -> None:
        """Add NICs and add their interfaces to the networks based on the defined networks.  # noqa: E501

        If a NIC is not present, it will be added.
        If a NIC is already present, it will be reused.
        If a NIC is no longer needed, it will be deleted.

        If an interface is no longer needed, it will be deleted from the network.
        If an interface is already present, it will be reused.
        If an interface is not present, it will be added to the network.
        """
        nodes = self.nodes
        networks = self.networks
        spare_ifaces: dict[tuple[str, str], list[Interface]] = {}
        for node_name, node in nodes.items():
            count = 0
            for _index, _kind, nw_name, network in self.iternetworks(
                site=node.get_site()
            ):
                # Add a NIC to the node, if needed
                nic_model = (
                    NIC_BASIC
                    if network.nic.kind == NIC_SHARED
                    else f"{NIC}_{network.nic.model.replace('-', '_')}"
                )
                key = (node_name, nic_model)
                if len(spare_ifaces.get(key, [])) == 0:
                    # Create a NIC
                    count += 1
                    name = (
                        network.nic.name
                        or f"{network.nic.kind}-{network.nic.model}-{count}"
                    )
                    logger.debug(
                        "Creating NIC <%s> with name <%s> on node <%s>",
                        nic_model,
                        name,
                        node_name,
                    )
                    nic = node.add_component(model=nic_model, name=name)

                    # Get the NIC's interface
                    ifaces = nic.get_interfaces()
                    for iface in ifaces:
                        iface.set_mode("manual")

                    spare_ifaces.setdefault(key, [])
                    spare_ifaces[key].extend(ifaces)

                # Assign an interface from the NIC to the FABRIC network
                net = networks[nw_name]
                iface = spare_ifaces[key].pop()
                logger.debug(
                    "Adding Interface <%s> of NIC <%s> with name <%s> to node <%s>",
                    iface.get_name(),
                    nic_model,
                    name,
                    node_name,
                )
                net.add_interface(iface)

    def configure_storage(self) -> None:
        """Configure storage on the nodes.

        For NVME storage, if a mount point is specified, it will be used to mount the
        NVMe device.
        For NAS storage, if auto mount is True, the device will be formatted if needed,
        then mounted on `/mnt/<storage-name>`.
        """
        nodes = self.nodes
        prefix = self.provider_conf.name_prefix

        for index_i, index_j, machine in self.itermachines():
            name = f"{prefix}-s{machine.site}-m{index_i}-n{index_j}"
            if machine.storage:
                count = 0
                for index, storage in enumerate(machine.storage):
                    if storage.kind == NVME and storage.mount_point:
                        nvme_name = f"{NVME}_{storage.model}-{count}"
                        count += 1
                        logger.debug(
                            "Configuring NVME <%s> on node <%s> with mount point <%s>",
                            nvme_name,
                            name,
                            storage.mount_point,
                        )
                        nodes[name].get_component(nvme_name).configure_nvme(
                            mount_point=storage.mount_point
                        )
                    elif storage.kind == STORAGE:
                        model = f"{storage.kind}_{storage.model}"
                        node = nodes[name]
                        device_name = node.get_storage(storage.name).get_device_name()

                        if storage.auto_mount is False:
                            logger.info(
                                "Storage <%s> available as device <%s> on node <%s>",
                                storage.name,
                                device_name,
                                name,
                            )
                            continue

                        logger.debug(
                            "Configuring Storage <%s> with name <%s> with auto_mount <%s> to node <%s>",  # noqa: E501
                            model,
                            storage.name,
                            storage.auto_mount,
                            name,
                        )

                        out, _err = node.execute(f"sudo blkid '{device_name}'")
                        if not out.strip():
                            logger.debug(
                                "Device <%s> is not formatted, running mkfs.xfs on it",
                                device_name,
                            )
                            node.execute(f"sudo mkfs.xfs '{device_name}'")

                        mount_point = f"/mnt/{storage.name}"
                        node.execute(
                            f"sudo mkdir -p '{mount_point}' ; "
                            f"sudo mount '{device_name}' '{mount_point}'"
                        )
                        logger.info(
                            "Storage <%s>, device <%s> mounted on <%s>",
                            storage.name,
                            device_name,
                            mount_point,
                        )

    def assign_public_ip(self) -> None:
        if self.has_public_ip is False:
            return

        # Make IP Publicly Routable
        slice = self.fablib.get_slice(name=self.provider_conf.name_prefix)
        for _index, kind, name, network in self.iternetworks():
            if "Ext" not in kind:
                continue

            net = slice.get_network(name=name)
            ip = net.get_available_ips()
            total_ips = len(net.get_interfaces())
            kwargs = {f"ipv{network.ip_version}": [str(_) for _ in ip[:total_ips]]}
            logger.debug("Making IPs <%s> publicly routable", kwargs)
            net.make_ip_publicly_routable(**kwargs)

    def configure_network_interfaces(self) -> None:
        networks = self.networks
        for _index, kind, name, network in self.iternetworks():
            net = networks[name]
            if kind.startswith("L2"):
                self.configure_l2network_interfaces(network, net, name)
            else:
                self.configure_l3network_interfaces(network, net, name)

    def configure_l2network_interfaces(
        self, network: NetworkConfigTypes, net: NetworkService, name: str
    ) -> None:
        """Configure network interfaces for each node."""
        subnet = network.network
        prefix_len = subnet.prefixlen
        logger.debug("Subnet for network <%s> is <%s>", name, subnet)
        ipiter = subnet.hosts()

        for iface in net.get_interfaces():
            ip = next(ipiter)
            node = iface.get_node()
            node_name = node.get_name()
            os_ifname = iface.get_physical_os_interface_name()

            logger.debug(
                "Configuring IP <%s> on node <%s> for network <%s>", ip, node_name, name
            )
            node.upload_directory(str(self.scripts_dir), "/tmp")
            cmd = (
                f"cd /tmp/{self.scripts_dir.name} ; chmod +x *.sh ; "
                f"sudo ./main.sh -t {network.kind} -I {os_ifname} -A {ip}/{prefix_len}"
            )
            logger.debug("Executing command <%s> on node <%s>", cmd, node_name)
            node.execute(cmd)

    def configure_l3network_interfaces(
        self, network: NetworkConfigTypes, net: NetworkService, name: str
    ) -> None:
        """Configure network interfaces for each node."""
        gateway = net.get_gateway()
        subnet = net.get_subnet()
        prefix_len = subnet.prefixlen
        network.network = subnet
        kind = network.kind
        logger.debug("Subnet for network <%s> is <%s>", name, subnet)

        if "Ext" in network.kind:
            ipiter = iter(net.get_public_ips())
        else:
            ipiter = subnet.hosts()
            next(ipiter)  # Skip first IP (usually gateway)

        for iface in net.get_interfaces():
            node = iface.get_node()
            node_name = node.get_name()
            os_ifname = iface.get_physical_os_interface_name()
            ip = next(ipiter)  # Get next available IP in subnet
            logger.debug(
                "Configuring IP <%s> on node <%s> for network <%s>", ip, node_name, name
            )
            node.upload_directory(str(self.scripts_dir), "/tmp")
            if "Ext" in network.kind:
                cmd = (
                    f"cd /tmp/{self.scripts_dir.name} ; chmod +x *.sh ; "
                    f"sudo ./main.sh -t {kind} -I {os_ifname} -A {ip}/{prefix_len} "
                    f"-G {gateway}"
                )
                logger.debug("Executing command <%s> on node <%s>", cmd, node_name)
                node.execute(cmd)
            else:
                cmd = (
                    f"cd /tmp/{self.scripts_dir.name} ; chmod +x *.sh ; "
                    f"sudo ./main.sh -t {kind} -I {os_ifname} -A {ip}/{prefix_len} "
                    f"-G {gateway}"
                )
                logger.debug("Executing command <%s> on node <%s>", cmd, node_name)
                node.execute(cmd)

    def refresh(self) -> None:
        slice = self.slice
        self.nodes = {n.get_name(): n for n in slice.get_nodes()}
        self.networks = {n.get_name(): n for n in slice.get_networks()}

    def create_roles(self) -> Roles:
        nodes = self.nodes
        roles = Roles()
        base_ssh_args = (
            "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            "-o ForwardAgent=yes"
        )
        proxy_cmd = (
            f"ssh -W %h:%p {base_ssh_args} -i '{self.gateway_private_key}' "
            f"-l '{self.gateway_user}' {self.gateway}"
        )
        for index_i, index_j, machine in self.itermachines():
            name_prefix = self.provider_conf.name_prefix
            site = machine.site
            name = f"{name_prefix}-s{site}-m{index_i}-n{index_j}"
            node = nodes[name]
            host = Host(
                address=str(node.get_management_ip()),
                user=node.get_username(),
                keyfile=self.private_key,
                extra={
                    "id": node.get_instance_name(),
                    "cores": node.get_cores(),
                    "mem": node.get_ram(),
                    "disk": node.get_disk(),
                    "slice": node.get_slice().get_name(),
                    "slice_id": node.get_slice().get_slice_id(),
                    "site": node.get_site(),
                    "name": name,
                    "management_ip": str(node.get_management_ip()),
                    "ssh": node.get_ssh_command(),
                    "ansible_ssh_common_args": f"{base_ssh_args} "
                    f'-o ProxyCommand="{proxy_cmd}" ',
                    "rc_file": self.provider_conf.rc_file,
                },
            )
            for role in machine.roles:
                roles[role] += [host]

        return roles

    def create_networks(self) -> Networks:
        networks = Networks()
        for _index, _kind, name, network in self.iternetworks():
            if isinstance(
                network,
                (Fabnetv6NetworkConfiguration, Fabnetv6ExternalNetworkConfiguration),
            ):
                net = self.networks[name]
                subnet = net.get_subnet()
                prefix_len = subnet.prefixlen
                for iface in net.get_interfaces():
                    ip = iface.get_ip_addr()
                    network.allocate_ip(IPv6Interface(f"{ip}/{prefix_len}"))

            net = FabricNetwork(config=network)
            for role in network.roles:
                networks[role] += [net]

        return networks

    def itermachines(self) -> Generator[tuple[int, int, Any], Any, None]:
        for index_i, machine in enumerate(self.provider_conf.machines, 1):
            for index_j in range(1, machine.number + 1):
                yield index_i, index_j, machine

    def iternetworks(
        self, site: str | None = None
    ) -> Generator[tuple[int, str, str, Any], Any, None]:
        for index, network in enumerate(self.provider_conf.networks, 1):
            kind = network.kind
            if network.name:
                yield index, network.kind, network.name, network
                continue

            prefix = f"{kind}-IPv{network.ip_version}"
            if kind.startswith("L2"):
                if kind == L2BRIDGE:
                    nw_name = f"{prefix}-{network.site}"
                    if site and network.site != site:
                        continue
                elif kind == L2STS:
                    nw_name = f"{prefix}-{network.site_1}-{network.site_2}"
                    if site and network.site_1 != site and network.site_2 != site:
                        continue
                else:
                    raise NotImplementedError(f"Unknown L2 network kind {kind}")
            else:
                nw_name = f"{prefix}-{network.site}"
                if site and network.site != site:
                    continue

            yield index, network.kind, nw_name, network

    def load_id_token(self) -> None:
        """Load the permissions from the fabric."""
        token_location = os.environ[Constants.FABRIC_TOKEN_LOCATION]
        token = json.load(open(token_location))
        id_token = token["id_token"].split(".")[1]
        # FABRIC tokens are not properly padded causing b64decode to fail
        id_token = id_token + "=" * (4 - (len(id_token) % 4))
        id_token_bytes = id_token.encode("ascii")
        token = json.loads(base64.b64decode(id_token_bytes).decode("utf-8"))
        self.project_name = token["projects"][0]["name"]
        self.project_uuid = token["projects"][0]["uuid"]
        self.permissions = set(token["projects"][0]["tags"])

    def check(self) -> None:
        """Check if the fabric resources are valid."""
        sites = self._check_machines()
        self._check_networks(sites)

    def _check_machines(self) -> set[str]:
        fablib = self.fablib
        machines = self.provider_conf.machines

        node_sites: set[str] = set()
        sites: list[str] = fablib.get_site_names()
        images: dict[str, dict] = fablib.get_image_names()

        if self.provider_conf.site and self.provider_conf.site not in sites:
            raise ValueError(f"Invalid FABRIC site <{self.provider_conf.site}>")

        if self.provider_conf.image and self.provider_conf.image not in images:
            raise ValueError(f"Invalid FABRIC image <{self.provider_conf.image}>")

        for index_i, machine in enumerate(machines, 1):
            if machine.site and machine.site not in sites:
                raise ValueError(
                    f"Invalid FABRIC site <{machine.site}> on machine {index_i}"
                )

            node_sites.add(machine.site or self.provider_conf.site)

            if machine.image and machine.image not in images:
                raise ValueError(
                    f"Invalid FABRIC image <{machine.image}> on machine {index_i}"
                )

            if machine.gpus and PERMISSION_GPU not in self.permissions:
                raise ValueError(f"GPU permission <{PERMISSION_GPU}> is required")

            self._check_storage(machine)

        if len(node_sites) > 1 and PERMISSION_SLICE_MULTISITE not in self.permissions:
            raise ValueError(
                f"Multisite permission <{PERMISSION_SLICE_MULTISITE}> is required"
            )

        return node_sites

    def _check_storage(self, machine: MachineConfiguration) -> None:
        for storage in machine.storage:
            if storage.kind == NVME and PERMISSION_NVME not in self.permissions:
                if (
                    storage.model == STORAGE_MODEL_P4510
                    and PERMISSION_NVME_P4510 not in self.permissions
                ):
                    raise ValueError(
                        f"NVME permission <{PERMISSION_NVME}> or "
                        f"<{PERMISSION_NVME_P4510}> is required"
                    )
            elif storage.kind == STORAGE and PERMISSION_STORAGE not in self.permissions:
                raise ValueError(
                    f"Storage permission <{PERMISSION_STORAGE}> is required"
                )

            if storage.kind == STORAGE and machine.number > 1:
                raise ValueError(
                    f"Storage <{storage.model}> <{storage.name}> can't be "
                    "mounted on more than one machine"
                )

    def _check_networks(self, sites: set[str]) -> None:
        nw_names = set()
        for index, kind, nw_name, network in self.iternetworks():
            if nw_name in nw_names:
                raise ValueError(
                    f"Network <{index}> <{nw_name}> is defined more than once, "
                    "consider assigning a unique name in the configuration"
                )

            nw_names.add(nw_name)
            if kind == FABNETV4EXT and PERMISSION_FABNETV4_EXT not in self.permissions:
                raise ValueError(
                    f"FABNETV4Ext permission <{PERMISSION_FABNETV4_EXT}> is required"
                )

            elif (
                kind == FABNETV6EXT and PERMISSION_FABNETV6_EXT not in self.permissions
            ):
                raise ValueError(
                    f"FABNETV6Ext permission <{PERMISSION_FABNETV6_EXT}> is required"
                )

            if (
                network.nic.kind == NIC_SMART
                and network.nic.model == NIC_MODEL_CONNECTX_5
                and PERMISSION_CONNECTX_5 not in self.permissions
            ):
                raise ValueError(
                    f"ConnectX_5 permission <{PERMISSION_CONNECTX_5}> is required"
                )
            elif (
                network.nic.kind == NIC_SMART
                and network.nic.model == NIC_MODEL_CONNECTX_6
                and PERMISSION_CONNECTX_6 not in self.permissions
            ):
                raise ValueError(
                    f"ConnectX_6 permission <{PERMISSION_CONNECTX_6}> is required"
                )

            if kind == L2STS:
                if network.site_1 not in sites:
                    raise ValueError(
                        f"No machines provisioned on site <{network.site_1}>"
                    )
                elif network.site_2 not in sites:
                    raise ValueError(
                        f"No machines provisioned on site <{network.site_2}>"
                    )
            elif network.site not in sites:
                raise ValueError(f"No machines provisioned on site <{network.site}>")

    def destroy(self, wait: bool = False, **kwargs):
        """Destroy all FABRIC nodes involved in the deployment."""
        with source_credentials_from_rc_file(self.provider_conf.rc_file):
            logger.info("Deleting FABRIC slice")
            fablib = FablibManager(log_propagate=True)
            fablib.delete_slice(slice_name=self.provider_conf.name_prefix)
            logger.info("Deleting FABRIC slice done")

    def offset_walltime(self, difference: int):
        pass

    def __getstate__(self):
        """Remove attributes that cannot be pickled."""
        state = self.__dict__.copy()
        for attr in ("fablib", "slice", "nodes", "networks"):
            del state[attr]
        return state

    def __setstate__(self, state):
        """Restore attributes from the pickled state."""
        self.__dict__.update(state)

        self.fablib = None
        self.slice = None
        self.nodes = {}
        self.networks = {}
