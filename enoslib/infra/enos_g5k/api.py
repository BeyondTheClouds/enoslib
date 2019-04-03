# -*- coding: utf-8 -*-

import copy
from itertools import groupby
from operator import itemgetter
import os

from grid5000 import Grid5000

from enoslib.infra.enos_g5k import remote
from enoslib.infra.enos_g5k import utils
from enoslib.infra.enos_g5k.driver import get_driver
from enoslib.infra.enos_g5k.constants import DEFAULT_ENV_NAME, JOB_TYPE_DEPLOY
from enoslib.infra.enos_g5k.schema import PROD


def exec_command_on_nodes(nodes, cmd, label, conn_params=None):
    """Execute a command on a node (id or hostname) or on a set of nodes.

    Args:
        nodes (list):  list of targets of the command cmd. Each must be an
    execo.Host.
        cmd (str): string representing the command to run on the remote nodes.
        label (str):  string for debugging purpose.
        conn_params (dict): connection parameters passed to the execo.Remote
    function.

    """

    remote.exec_command_on_nodes(nodes, cmd, label, conn_params)


def _get_grid5000_client():
    conf_file = os.path.join(os.environ.get("HOME"), ".python-grid5000.yaml")
    return Grid5000.from_yaml(conf_file)


class Resources:
    """Class to manipulate g5k resource.

    This acts as an entry point to control the deployment life-cycle.
    A typical workflow of use would be :

    Examples:
        .. code-block:: python

            configuration = { ... }
            r = Resources(configuration)
            r.reserve()
            r.deploy()
            r.configure_network()

        Or more concisely :

            configuration = { ... }
            r = Resources(configuration)
            r.launch()

    Note that ``configuration`` dict is not validated here, but can be through
    the :py:func:`enoslib.infra.enos_g5k.schema.validate_schema` function and
    thus follow the same syntax as the g5k provider.
    """

    def __init__(self, configuration):
        self.configuration = configuration
        # This one will be modified
        self.c_resources = copy.deepcopy(self.configuration["resources"])
        # Load the driver that will interact with G5K
        self.gk = _get_grid5000_client()
        self.driver = get_driver(configuration, self.gk)

    def launch(self):
        self.reserve()
        if self.configuration.get("job_type") == JOB_TYPE_DEPLOY:
            self.deploy()
            self.configure_network()
        else:
            self.grant_root_access()

    def reserve(self):
        nodes, networks = self.driver.reserve()

        # The following as side-effect on self.c_resources
        self._concretize_resources(nodes, networks)

    def deploy(self):
        def translate_vlan(primary_network, networks, nodes):

            def translate(node, vlan_id):
                splitted = node.split(".")
                splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
                return ".".join(splitted)

            if utils.is_prod(primary_network, networks):
                return nodes
            net = utils.lookup_networks(primary_network, networks)
            vlan_id = net["_c_network"].vlan_id
            return [translate(node, vlan_id) for node in nodes]

        env_name = self.configuration.get("env_name", DEFAULT_ENV_NAME)
        force_deploy = self.configuration.get("force_deploy", False)

        machines = self.c_resources["machines"]
        networks = self.c_resources["networks"]
        key = itemgetter("primary_network")
        s_machines = sorted(machines, key=key)
        for primary_network, i_descs in groupby(s_machines, key=key):
            descs = list(i_descs)
            nodes = [desc.get("_c_nodes", []) for desc in descs]
            # flatten
            nodes = sum(nodes, [])
            options = {
                "env_name": env_name
            }

            net = utils.lookup_networks(primary_network, networks)
            if net["type"] != PROD:
                options.update({"vlan": net["_c_network"].vlan_id})
            site = net["site"]
            # Yes, this is sequential
            deployed, undeployed = self.driver.deploy(site, nodes,
                                                      force_deploy, options)
            for desc in descs:
                c_nodes = desc.get("_c_nodes", [])
                desc["_c_deployed"] = list(set(c_nodes) & set(deployed))
                desc["_c_undeployed"] = list(set(c_nodes) & set(undeployed))
                desc["_c_ssh_nodes"] = translate_vlan(
                    primary_network,
                    networks,
                    desc["_c_deployed"])

    def configure_network(self):
        dhcp = self.configuration.get("dhcp", False)
        utils.mount_nics(self.gk, self.c_resources)
        if dhcp:
            utils.dhcp_interfaces(self.c_resources)
        return self.c_resources

    def grant_root_access(self):
        utils.grant_root_access(self.c_resources)

    def get_networks(self):
        """Get the networks assoiated with the resource description.

        Returns
            list of tuple roles, network
        """
        networks = self.c_resources["networks"]
        result = []
        for net in networks:
            _c_network = net.get("_c_network")
            if _c_network is None:
                continue
            roles = utils.get_roles_as_list(net)
            result.append((roles, _c_network))
        return result

    def get_roles(self):
        """Get the roles associated with the hosts.

        Returns
            dict of role -> [host]
        """

        machines = self.c_resources["machines"]
        result = {}
        for desc in machines:
            roles = utils.get_roles_as_list(desc)
            hosts = self._denormalize(desc)
            for role in roles:
                result.setdefault(role, [])
                result[role].extend(hosts)
        return result

    def destroy(self):
        """Destroy the associated job."""
        self.driver.destroy()

    def _denormalize(self, desc):
        hosts = desc.get("_c_ssh_nodes", desc.get("_c_nodes", []))
        nics = desc.get("_c_nics", [])
        hosts = [{"host": h, "nics": nics} for h in hosts]
        return hosts

    def _concretize_resources(self, nodes, networks):
        self._concretize_nodes(nodes)
        self._concretize_networks(networks)

    def _concretize_nodes(self, nodes):
        utils.concretize_nodes(self.c_resources, nodes)

    def _concretize_networks(self, networks):
        utils.concretize_networks(self.c_resources, networks)
