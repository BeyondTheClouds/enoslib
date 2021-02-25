# -*- coding: utf-8 -*-
from collections import defaultdict
import os

from enoslib.errors import EnosFilePathError


def get_roles_as_list(desc):
    # NOTE(msimonin): role and roles are mutually exclusive in theory We'll fix
    # the schemas later in the mean time to not break user code let's remove
    # duplicates here
    roles = desc.get("roles", [])
    if roles:
        return roles

    role = desc.get("role", [])
    if role:
        roles = [role]

    return roles


def gen_rsc(roles):
    for _, hosts in roles.items():
        for host in hosts:
            yield host


def _check_tmpdir(tmpdir):
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    else:
        if not os.path.isdir(tmpdir):
            raise EnosFilePathError("%s is not a directory" % tmpdir)
        else:
            pass


def remove_hosts(roles, hosts_to_keep):
    updated_roles = defaultdict(list)
    for role, hosts in roles.items():
        for host in hosts:
            if host.alias in hosts_to_keep:
                updated_roles[role].append(host)
    return updated_roles
