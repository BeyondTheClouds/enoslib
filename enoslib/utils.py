# -*- coding: utf-8 -*-

from enoslib.errors import EnosFilePathError

import re
import os


def get_roles_as_list(desc):
    roles = desc.get("role", [])
    if roles:
        roles = [roles]
    roles.extend(desc.get("roles", []))
    return roles


def gen_rsc(roles):
    for _, hosts in roles.items():
        for host in hosts:
            yield host


def _expand_groups(grp):
    """Expand group names.
    e.g:
        * grp[1-3] -> [grp1, grp2, grp3]
        * grp1 -> [grp1]
    """
    p = re.compile("(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\]")
    m = p.match(grp)
    if m is not None:
        s = int(m.group('start'))
        e = int(m.group('end'))
        n = m.group('name')
        return map(lambda x: n + str(x), range(s, e + 1))
    else:
        return [grp]


def _check_tmpdir(tmpdir):
    if not os.path.exists(tmpdir):
        os.mkdir(tmpdir)
    else:
        if not os.path.isdir(tmpdir):
            raise EnosFilePathError("%s is not a directory" % tmpdir)
        else:
            pass
