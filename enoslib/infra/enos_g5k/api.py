# -*- coding: utf-8 -*-

import copy
from itertools import groupby

from .remote import get_execo_remote, DEFAULT_CONN_PARAMS
from .driver import get_driver
from .constants import DEFAULT_ENV_NAME, JOB_TYPE_DEPLOY, PROD
import enoslib.infra.enos_g5k.utils as utils


def _translate_vlan(primary_network, networks, nodes, reverse=False):
    def translate(node, vlan_id):
        if not reverse:
            splitted = node.split(".")
            splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
            return ".".join(splitted)
        else:
            node = node.replace("-kavlan-%s" % vlan_id, "")
            return node

    if utils.is_prod(primary_network, networks):
        return nodes
    net = utils.lookup_networks(primary_network, networks)
    # There can be only one network in the vlan case...
    vlan_id = net["_c_network"][0].vlan_id
    return [translate(node, vlan_id) for node in nodes]


def _check_deployed_nodes(nodes):
    """This is borrowed from execo."""
    deployed = []
    undeployed = []
    cmd = "! (mount | grep -E '^/dev/[[:alpha:]]+2 on / ')"

    deployed_check = get_execo_remote(
        cmd,
        nodes,
        DEFAULT_CONN_PARAMS)

    for p in deployed_check.processes:
        p.nolog_exit_code = True
        p.nolog_timeout = True
        p.nolog_error = True
        p.timeout = 10
    deployed_check.run()

    for p in deployed_check.processes:
        if p.ok:
            deployed.append(p.host.address)
        else:
            undeployed.append(p.host.address)

    return deployed, undeployed


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

    def __init__(self, configuration, client=None):
        self.configuration = configuration
        # This one will be modified
        self.c_resources = copy.deepcopy(self.configuration["resources"])
        self.driver = get_driver(configuration)

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
        def _key(desc):
            """Get the site and the primary network of a description.

            Prerequesite: the desc must have some concrete nodes attached.
            """
            site = desc["_c_nodes"][0].split(".")[1]
            net = desc["primary_network"]
            return site, net

        env_name = self.configuration.get("env_name", DEFAULT_ENV_NAME)
        force_deploy = self.configuration.get("force_deploy", False)

        machines = self.c_resources["machines"]
        networks = self.c_resources["networks"]
        # Get rid of empty groups if any
        # There's nothing to deploy for such description
        s_machines = [m for m in machines if m.get("_c_nodes", [])]
        s_machines = sorted(s_machines, key=_key)
        for (site, primary_network), i_descs in groupby(s_machines, key=_key):
            descs = list(i_descs)
            nodes = [desc.get("_c_nodes", []) for desc in descs]
            # flatten
            nodes = sum(nodes, [])
            options = {
                "env_name": env_name
            }

            net = utils.lookup_networks(primary_network, networks)
            if net["type"] != PROD:
                options.update({"vlan": net["_c_network"][0].vlan_id})

            # Yes, this is sequential
            deployed, undeployed = [], nodes
            if not force_deploy:
                deployed, undeployed = _check_deployed_nodes(
                    _translate_vlan(primary_network, networks, nodes))
                deployed = _translate_vlan(primary_network, networks, deployed,
                                          reverse=True)
                undeployed = _translate_vlan(primary_network, networks,
                                              undeployed, reverse=True)

            if force_deploy or not deployed:
                deployed, undeployed = self.driver.deploy(site, nodes, options)

            for desc in descs:
                c_nodes = desc.get("_c_nodes", [])
                desc["_c_deployed"] = list(set(c_nodes) & set(deployed))
                desc["_c_undeployed"] = list(set(c_nodes) & set(undeployed))
                desc["_c_ssh_nodes"] = _translate_vlan(
                    primary_network,
                    networks,
                    desc["_c_deployed"])

    def configure_network(self):
        dhcp = self.configuration.get("dhcp", False)
        utils.mount_nics(self.c_resources)
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
