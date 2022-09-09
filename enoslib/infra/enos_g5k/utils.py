from enoslib.log import getLogger

logger = getLogger(__name__, ["G5k"])


def inside_g5k():
    import socket

    return socket.gethostname().endswith("grid5000.fr")
