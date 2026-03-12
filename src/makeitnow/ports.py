"""Find the next available TCP port on the local machine."""

import socket


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if *port* is already in use (bound) on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return False  # bind succeeded → port is free
        except OSError:
            return True   # bind failed → port is in use


def find_free_port(start: int = 8080, stop: int = 9999) -> int:
    """Return the first free port in [*start*, *stop*].

    Raises RuntimeError if no free port is found in the range.
    """
    for port in range(start, stop + 1):
        if not is_port_open(port):
            return port
    raise RuntimeError(
        f"No free port found in range {start}–{stop}. "
        "Try a different --port-start value."
    )
