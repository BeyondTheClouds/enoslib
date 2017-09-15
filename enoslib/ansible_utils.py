# -*- coding: utf-8 -*-
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from collections import namedtuple
from errors import EnosFailedHostsError, EnosUnreachableHostsError

import logging


def run_ansible(playbooks, inventory_path, extra_vars={},
        tags=None, on_error_continue=False):
    """Runs ansible playbooks

    :param playbooks: list of the paths to playbooks to run.

    :param inventory_path: path to the inventory.

    :param extra_vars: extra_vars to pass to ansible. This is equivalent
    to the -e switch of the ansible cli.

    :param tags: run only runs tasks with the given tag

    :param on_error_continue: True iff execution should continue after on error
    """
    extra_vars = extra_vars or {}
    variable_manager = VariableManager()
    loader = DataLoader()

    inventory = Inventory(loader=loader,
        variable_manager=variable_manager,
        host_list=inventory_path)

    variable_manager.set_inventory(inventory)

    if extra_vars:
        variable_manager.extra_vars = extra_vars

    if tags is None:
        tags = []

    passwords = {}
    # NOTE(msimonin): The ansible api is "low level" in the
    # sense that we are redefining here all the default values
    # that are usually enforce by ansible called from the cli
    Options = namedtuple("Options", ["listtags", "listtasks",
                                     "listhosts", "syntax",
                                     "connection", "module_path",
                                     "forks", "private_key_file",
                                     "ssh_common_args",
                                     "ssh_extra_args",
                                     "sftp_extra_args",
                                     "scp_extra_args", "become",
                                     "become_method", "become_user",
                                     "remote_user", "verbosity",
                                     "check", "tags", "pipelining"])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection="ssh",
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=None,
                      become_method="sudo", become_user="root",
                      remote_user=None, verbosity=2, check=False,
                      tags=tags, pipelining=True)

    for path in playbooks:
        logging.info("Running playbook %s with vars:\n%s" % (path, extra_vars))

        pbex = PlaybookExecutor(
            playbooks=[path],
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=options,
            passwords=passwords
        )

        code = pbex.run()
        stats = pbex._tqm._stats
        hosts = stats.processed.keys()
        result = [{h: stats.summarize(h)} for h in hosts]
        results = {"code": code, "result": result, "playbook": path}
        print(results)

        failed_hosts = []
        unreachable_hosts = []

        for h in hosts:
            t = stats.summarize(h)
            if t["failures"] > 0:
                failed_hosts.append(h)

            if t["unreachable"] > 0:
                unreachable_hosts.append(h)

        if len(failed_hosts) > 0:
            logging.error("Failed hosts: %s" % failed_hosts)
            if not on_error_continue:
                raise EnosFailedHostsError(failed_hosts)
        if len(unreachable_hosts) > 0:
            logging.error("Unreachable hosts: %s" % unreachable_hosts)
            if not on_error_continue:
                raise EnosUnreachableHostsError(unreachable_hosts)

def generate_inventory(roles):
    """Generates an inventory files from roles

    :param roles: dict of roles (roles -> list of Host)
    """
    inventory = []
    for role, desc in roles.items():
        inventory.append("[%s]" % role)
        inventory.extend([_generate_inventory_string(d) for d in desc])
    return "\n".join(inventory)

def _generate_inventory_string(host):
    i = [host.alias, "ansible_host=%s" % host.address]
    if host.user is not None:
        i.append("ansible_ssh_user=%s" % host.user)
    if host.port is not None:
        i.append("ansible_port=%s" % host.port)
    if host.keyfile is not None:
        i.append("ansible_ssh_private_key_file=%s" % host.keyfile)
    # Disabling hostkey ckecking
    common_args = []
    common_args.append("-o StrictHostKeyChecking=no")
    common_args.append("-o UserKnownHostsFile=/dev/null")
    forward_agent = host.extra.get('forward_agent', False)
    if forward_agent:
        common_args.append("-o ForwardAgent=yes")

    gateway = host.extra.get('gateway', None)
    if gateway is not None:
        proxy_cmd = ["ssh -W %h:%p"]
        # Disabling also hostkey checking for the gateway
        proxy_cmd.append("-o StrictHostKeyChecking=no")
        proxy_cmd.append("-o UserKnownHostsFile=/dev/null")
        gateway_user = host.extra.get('gateway_user', host.user)
        if gateway_user is not None:
            proxy_cmd.append("-l %s" % gateway_user)

        proxy_cmd.append(gateway)
        proxy_cmd = " ".join(proxy_cmd)
        common_args.append("-o ProxyCommand=\"%s\"" % proxy_cmd)

    common_args = " ".join(common_args)
    i.append("ansible_ssh_common_args='%s'" % common_args)

    # Add custom variables
    for k, v in host.extra.items():
        if k not in ["gateway", "gateway_user", "forward_agent"]:
            i.append("%s=%s" % (k, v))
    return " ".join(i)
