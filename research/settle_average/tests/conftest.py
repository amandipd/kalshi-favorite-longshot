"""Tests for the settle-average research: put research/settle_average on the path and keep the network shut."""
import socket
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here may reach Kalshi: a fake that misses a request fails it instead of going out."""
    def refuse(*args, **kwargs):
        raise OSError("the settle_average tests never use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
