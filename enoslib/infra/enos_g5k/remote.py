# -*- coding: utf-8 -*-

import logging

import execo as ex


logger = logging.getLogger(__name__)


BASESTRING = str


DEFAULT_CONN_PARAMS = {'user': 'root'}


def exec_command_on_nodes(nodes, cmd, label, conn_params=None):
    """Execute a command on a node (id or hostname) or on a set of nodes.

    :param nodes:       list of targets of the command cmd. Each must be an
                        execo.Host.
    :param cmd:         string representing the command to run on the
                        remote nodes.
    :param label:       string for debugging purpose.
    :param conn_params: connection parameters passed to the execo.Remote
                        function
    """

    if isinstance(nodes, BASESTRING):
        nodes = [nodes]

    if conn_params is None:
        conn_params = DEFAULT_CONN_PARAMS

    logger.debug("Running %s on %s ", label, nodes)
    remote = ex.get_remote(cmd, nodes, conn_params)
    remote.run()
    if not remote.finished_ok:
        raise Exception('An error occcured during remote execution')
    return remote


def get_execo_remote(*args, **kwargs):
    return ex.get_remote(*args, **kwargs)
