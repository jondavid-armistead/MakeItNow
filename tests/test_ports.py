"""Tests for port detection."""

import socket
from makeitnow.ports import find_free_port, is_port_open


def test_is_port_open_free():
    # Find a random free port via OS, then immediately check it's not in use
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # Socket released — port should be free
    assert not is_port_open(port)


def test_is_port_open_bound():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        assert is_port_open(port)


def test_find_free_port_returns_int():
    port = find_free_port(start=19000, stop=19100)
    assert isinstance(port, int)
    assert 19000 <= port <= 19100


def test_find_free_port_is_actually_free():
    port = find_free_port(start=19000, stop=19100)
    assert not is_port_open(port)
