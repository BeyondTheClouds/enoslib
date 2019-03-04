from ansible.inventory.manager import InventoryManager as Inventory
from ansible.parsing.dataloader import DataLoader


class EnosInventory(Inventory):

    def __init__(self, loader=None, sources=None, roles=None):

        if sources is None and roles is None:
            raise ValueError("sources or roles mus be set")

        if loader is None:
            loader = DataLoader()
        super(EnosInventory, self).__init__(loader, sources=sources)

        # We add the roles as defined in roles
        if roles is None:
            roles = {}

        self._populate_with_roles(roles)

    def _populate_with_roles(self, roles):

        for role, machines in roles.items():
            self.add_group(role)
            for machine in machines:
                self.add_host(machine.alias, group=role)
                # let's add some variabe to that host
                host = self.get_host(machine.alias)
                host.address = machine.address
                if machine.user is not None:
                    host.set_variable("ansible_ssh_user", machine.user)
                if machine.port is not None:
                    host.set_variable("ansible_port", machine.port)
                if machine.keyfile is not None:
                    host.set_variable("ansible_ssh_private_key_file",
                                      machine.keyfile)
                common_args = []
                common_args.append("-o StrictHostKeyChecking=no")
                common_args.append("-o UserKnownHostsFile=/dev/null")
                forward_agent = machine.extra.get('forward_agent', False)
                if forward_agent:
                    common_args.append("-o ForwardAgent=yes")

                gateway = machine.extra.get('gateway', None)
                if gateway is not None:
                    proxy_cmd = ["ssh -W %h:%p"]
                    # Disabling also hostkey checking for the gateway
                    proxy_cmd.append("-o StrictHostKeyChecking=no")
                    proxy_cmd.append("-o UserKnownHostsFile=/dev/null")
                    gateway_user = machine.extra.get('gateway_user',
                                                     machine.user)
                    if gateway_user is not None:
                        proxy_cmd.append("-l %s" % gateway_user)

                    proxy_cmd.append(gateway)
                    proxy_cmd = " ".join(proxy_cmd)
                    common_args.append("-o ProxyCommand=\"%s\"" % proxy_cmd)

                common_args = " ".join(common_args)
                host.set_variable("ansible_ssh_common_args",
                                  "{}".format(common_args))

                for k, v in machine.extra.items():
                    if k not in ["gateway", "gateway_user", "forward_agent"]:
                        host.set_variable(k, v)

        self.reconcile_inventory()

    def to_ini_string(self):

        def to_inventory_string(v):
            """Handle the cas of List[String]."""
            if isinstance(v, list):
                # [a, b, c] -> "['a','b','c']"
                s = map(lambda x: "'%s'" % x, v)
                s = "\"[%s]\"" % ','.join(s)
                return s
            return "'{}'".format(v)

        s = []
        for role, hostnames in self.get_groups_dict().items():
            s.append("[{}]".format(role))
            for hostname in hostnames:
                h = self.get_host(hostname)
                i = ["ansible_host={}".format(h.address)]
                # NOTE(mimonin): The intend of generating an ini is because we
                # want an inventory_file and and inventory dir set so removing
                # those keys (None values).
                for k, v in h.vars.items():
                    if k in ["inventory_file", "inventory_dir"]:
                        continue
                    i.append("{}={}".format(k, to_inventory_string(v)))
                # For determinism purpose (e.g unit tests)
                i = sorted(i)
                # Adding the inventory_hostname in front of the line
                i = [h.name, ] + i
                s.append(" ".join(i))
        return "\n".join(s)
