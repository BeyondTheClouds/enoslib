from pathlib import Path

from enoslib.log import getLogger

logger = getLogger(__name__, ["G5k"])


def inside_g5k() -> bool:
    import socket

    return socket.getfqdn().endswith("grid5000.fr")


def get_ssh_keys() -> str:
    """
    Retrieves the content of all public SSH keyfiles found in ~/.ssh folder

    Returns:
        str: The content of all public SSH keyfiles found.

    Raises:
        FileNotFoundError: If ~/.ssh doesn't exist, or is empty.
        ValueError: If SSH key files are empty.
    """
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        raise FileNotFoundError("No .ssh folder found, please create a SSH key.")
    key_files = list(ssh_dir.glob("*.pub"))
    if not key_files:
        raise FileNotFoundError("No public SSH key found, please create one.")
    keys_content = "\n".join(path.read_text() for path in key_files)
    if keys_content.strip():
        return keys_content
    raise ValueError("Empty SSH key files, please fix it.")
