# -*- coding: utf-8 -*-
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory import Inventory
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from collections import namedtuple

import logging


def run_ansible(playbooks, inventory_path, extra_vars={},
        tags=None, on_error_continue=False):
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
    Options = namedtuple('Options', ['listtags', 'listtasks',
                                     'listhosts', 'syntax',
                                     'connection', 'module_path',
                                     'forks', 'private_key_file',
                                     'ssh_common_args',
                                     'ssh_extra_args',
                                     'sftp_extra_args',
                                     'scp_extra_args', 'become',
                                     'become_method', 'become_user',
                                     'remote_user', 'verbosity',
                                     'check', 'tags', 'pipelining'])

    options = Options(listtags=False, listtasks=False,
                      listhosts=False, syntax=False, connection='ssh',
                      module_path=None, forks=100,
                      private_key_file=None, ssh_common_args=None,
                      ssh_extra_args=None, sftp_extra_args=None,
                      scp_extra_args=None, become=None,
                      become_method='sudo', become_user='root',
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
        results = {'code': code, 'result': result, 'playbook': path}
        print(results)

        failed_hosts = []
        unreachable_hosts = []

        for h in hosts:
            t = stats.summarize(h)
            if t['failures'] > 0:
                failed_hosts.append(h)

            if t['unreachable'] > 0:
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
    def to_inventory_hostname(d):
        s = []
        s.append("%s" % d["host"])
        s.append("ansible_user=root")
        for nic, roles in d["nics"]:
            s.extend([" %s=%s " % (role, nic) for role in roles])
        return " ".join(s)

    inventory = []
    for role, desc in roles.items():
        inventory.append("[%s]" % role)
        inventory.extend([to_inventory_hostname(d) for d in desc])
    return "\n".join(inventory)
