"""Shared fixtures for the maker shadow tests: no test may reach the network or the real Kalshi key.

Every test runs offline. The autouse guard makes any socket connection fail, so a test that forgot to fake Kalshi's
WebSocket, its REST API or ssh fails loudly instead of touching the live feed or the server.

    python -m pytest research/maker_shadow/tests -q
"""
import os
import socket
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                                   # research/maker_shadow
sys.path.insert(1, os.path.join(os.path.dirname(HERE), "..", "..", "bot", "kalshi_bot"))  # the bot's kalshi.py


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("a test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
