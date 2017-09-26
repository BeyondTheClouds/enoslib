from itertools import groupby
from operator import itemgetter, add
import enoslib.infra.enos_g5k.utils as utils
import copy

ENV_NAME = "jessie-x64-nfs"
JOB_NAME = "deploy5k"
WALLTIME = "02:00:00"


class Resources:

    def __init__(self, resources):
        self.resources = resources
        # This one will be modified
        self.c_resources = copy.deepcopy(resources)

    def launch(self, **kwargs):
        self.reserve(**kwargs)
        self.deploy(**kwargs)
        self.configure_network(**kwargs)

    def reserve(self, **kwargs):
        job_name = kwargs.get("job_name", JOB_NAME)
        walltime = kwargs.get("walltime", WALLTIME)
        gridjob = utils.get_or_create_job(self.c_resources, job_name, walltime)
        utils.concretize_resources(self.c_resources, gridjob)

    def deploy(self, **kwargs):
        def translate_vlan(primary_network, networks, nodes):

            def translate(node, vlan_id):
                splitted = node.split(".")
                splitted[0] = "%s-kavlan-%s" % (splitted[0], vlan_id)
                return ".".join(splitted)

            if utils.is_prod(primary_network, networks):
                return nodes
            net = utils.lookup_networks(primary_network, networks)
            vlan_id = net["_c_network"]["vlan_id"]
            return [translate(node, vlan_id) for node in nodes]
        env_name = kwargs.get("env_name", ENV_NAME)
        force_deploy = kwargs.get("force_deploy", False)

        machines = self.c_resources["machines"]
        networks = self.c_resources["networks"]
        key = itemgetter("primary_network")
        s_machines = sorted(machines, key=key)
        for primary_network, i_descs in groupby(s_machines, key=key):
            descs = list(i_descs)
            nodes = [desc.get("_c_nodes", []) for desc in descs]
            nodes = reduce(add, nodes)
            options = {
                "env_name": env_name
            }
            if not utils.is_prod(primary_network, networks):
                net = utils.lookup_networks(primary_network, networks)
                options.update({"vlan": net["_c_network"]["vlan_id"]})
            # Yes, this is sequential
            deployed, undeployed = utils._deploy(nodes, force_deploy, options)
            for desc in descs:
                c_nodes = desc.get("_c_nodes", [])
                desc["_c_deployed"] = list(set(c_nodes) & set(deployed))
                desc["_c_undeployed"] = list(set(c_nodes) & set(undeployed))
                desc["_c_ssh_nodes"] = translate_vlan(
                    primary_network,
                    networks,
                    desc["_c_deployed"])

    def configure_network(self, **kwargs):
        dhcp = kwargs.get("dhcp", False)
        utils.mount_nics(self.c_resources)
        # TODO(msimonin): run dhcp if asked
        if dhcp:
            utils.dhcp_interfaces(self.c_resources)
        return self.c_resources

    def get_networks(self):
        """Get the networks assoiated with the resource description.

        Returns
            list of networks
        """
        networks = self.c_resources["networks"]
        result = []
        for net in networks:
            current = {}
            current.update(net)
            _c_network = current.pop("_c_network", None)
            if _c_network:
                current.update(_c_network)
            result.append(current)
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
            for r in roles:
                result.setdefault(r, [])
                result[r].extend(hosts)
        return result

    def _denormalize(self, desc):
            hosts = desc.get("_c_ssh_nodes", [])
            nics = desc.get("_c_nics", [])
            hosts = [{"host": h, "nics": nics} for h in hosts]
            return hosts
