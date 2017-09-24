import execo as ex
import logging

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
    if isinstance(nodes, basestring):
        nodes = [nodes]

    if conn_params is None:
        conn_params = DEFAULT_CONN_PARAMS

    logging.debug("Running %s on %s " % (label, nodes))
    remote = ex.Remote(cmd, nodes, conn_params)
    remote.run()
