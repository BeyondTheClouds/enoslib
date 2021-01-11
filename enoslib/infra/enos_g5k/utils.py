# -*- coding: utf-8 -*-
from itertools import groupby

from operator import itemgetter
from typing import Dict, List, Tuple
import logging

from . import remote


logger = logging.getLogger(__name__)


def run_commands(hosts_cmds: List[Tuple[str, str]], conn_params: Dict):
    _hosts_cmds = sorted(hosts_cmds, key=itemgetter(1))
    for cmd, i_hosts_cmds in groupby(_hosts_cmds, key=itemgetter(1)):
        hosts = [_hc[0] for _hc in i_hosts_cmds]
        if cmd != "":
            remote.exec_command_on_nodes(hosts, cmd, cmd, conn_params)
