from enoslib.log import getLogger

logger = getLogger(__name__, ["G5k"])


def inside_g5k() -> bool:
    import socket

    return socket.getfqdn().endswith("grid5000.fr")
