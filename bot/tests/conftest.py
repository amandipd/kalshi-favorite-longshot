"""A safety net for every bot test: none can reach the state/ folder beside the code, where the live bot keeps its
ledger and reads its halt switch (a halt.json a test left there would stop real trading). Each test starts pointed at
a throwaway state folder of its own, whether or not it sets one itself, and the run fails if a halt.json appeared in
the real folder while it ran.

The one-bot lock is pointed at port 0 too, which is always free, so a test's bot never finds the running live bot's
port taken.

No test starts the paper fast entry's reader either, a background thread that would ask NTP servers and Kalshi:
bot.start_reader is swapped for a stub that does nothing, unless the test is marked real_reader (start_reader's own
tests, which stub the reader and the Kalshi client themselves).

No test asks a real time server (NTP, over UDP port 123) either. The dashboard keeps internet time (test_real_clock.py):
dashboard.clock() checks it every CLOCK_EVERY s on a daemon thread of its own, named "internet-clock", through
fast_entry.ntp_offset. Every test gets the fixture `fake_ntp` in ntp_offset's place, a stub that:
- answers a fixed offset of 0.0 s unless the test sets another: fake_ntp.offset is seconds, None (no server answered),
  or an exception, which it raises;
- notes the thread of each call (fake_ntp.calls) and sets fake_ntp.called;
- holds its answer while the test says so (fake_ntp.hold() ... fake_ntp.release()), up to HOLD_FOR s;
- lists the dashboard's check threads still running (fake_ntp.checks()) and waits for them all to finish
  (fake_ntp.wait()), so a test sees what the check read: that's how a test awaits the check.
Before each test the dashboard's reading, dashboard._clock, goes back to a copy of what it was at import (no reading, no
attempt), so nothing carries over from one test to the next; after each, a held answer is let go and the check threads
are waited for, so none writes into the next test's reading. ntp_offset's own tests (marked real_ntp:
test_fast_entry_ntp.py, which hands it fake sockets) get the real one. Under every test, real or stubbed, a datagram sent
to port 123 raises OSError (ntp_offset passes such a server over) and fails the test.
"""
import copy
import os
import socket
import threading

import pytest

from kalshi_bot import bot, fast_entry
from kalshi_bot.web import dashboard
from layout import BOT

REAL_STATE = os.path.normcase(os.path.join(BOT, "state"))   # the bot/ folder's own state/: no test may reach it
REAL_HALT = os.path.join(REAL_STATE, "halt.json")
REAL_HALT_AT_START = os.path.exists(REAL_HALT)

CLOCK_THREAD = "internet-clock"                     # the name of the dashboard's internet-time check's thread
PRISTINE_CLOCK = copy.copy(getattr(dashboard, "_clock", None))   # the dashboard's reading at import: none yet
REAL_NTP_OFFSET = fast_entry.ntp_offset             # the real one, for the guard's own test
HOLD_FOR = 5.0                                      # seconds a held answer waits at most for its release
NTP_PORT = 123
_REAL_SENDTO = socket.socket.sendto


def pytest_configure(config):
    config.addinivalue_line("markers", "real_reader: the test gets bot.py's own start_reader, not conftest.py's stub")
    config.addinivalue_line("markers", "real_ntp: the test gets fast_entry's own ntp_offset, not conftest.py's fake_ntp")


@pytest.fixture(autouse=True)
def throwaway_state(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(tmp_path_factory.mktemp("guard") / "state"))
    monkeypatch.setattr(bot, "BOT_PORT", 0, raising=False)
    yield
    assert os.path.normcase(os.path.abspath(bot.STATE)) != REAL_STATE, "a test pointed bot.STATE at the real state folder"


@pytest.fixture(autouse=True)
def no_mark_reader(request, monkeypatch):
    if request.node.get_closest_marker("real_reader") is None:
        monkeypatch.setattr(bot, "start_reader", lambda bot, env: None)


class FakeNtp:
    """fast_entry.ntp_offset for the tests: no network, an answer the test picks, and a way to wait for the check."""

    def __init__(self):
        self.offset = 0.0              # what it answers: seconds real time is ahead of the PC, None, or an exception to raise
        self.calls = []                # the thread each call came on
        self.called = threading.Event()
        self.gate = None               # while hold()ing: the event each call waits for
        self.stuck = 0                 # calls that waited HOLD_FOR s and were never released
        self.reached = []              # (host, 123) addresses something tried to send a datagram to: always a failure

    def __call__(self, *args, **kwargs):
        self.calls.append(threading.current_thread())
        self.called.set()
        gate = self.gate
        if gate is not None and not gate.wait(HOLD_FOR):
            self.stuck += 1
        if isinstance(self.offset, BaseException):
            raise self.offset
        return self.offset

    def hold(self):
        """From now on each call waits until release() (HOLD_FOR s at most): a check that's still running."""
        self.gate = threading.Event()

    def release(self):
        gate, self.gate = self.gate, None
        if gate is not None:
            gate.set()

    def checks(self):
        """The dashboard's internet-time check threads still running."""
        return [t for t in threading.enumerate() if t.name == CLOCK_THREAD]

    def wait(self, timeout=HOLD_FOR + 1):
        """Wait until every check started so far has finished (each thread named internet-clock, and any thread that
        called this stub), so whatever it read is in the dashboard's reading."""
        me = threading.current_thread()
        for t in self.checks() + self.calls:
            if t is not me and t.is_alive():
                t.join(timeout)
                assert not t.is_alive(), f"the dashboard's internet-time check (thread {t.name!r}) didn't finish in {timeout} s"


@pytest.fixture(autouse=True)
def fake_ntp(request, monkeypatch):
    ntp = FakeNtp()

    def sendto(sock, data, *args):
        address = args[-1] if args else None
        if sock.type == socket.SOCK_DGRAM and isinstance(address, tuple) and len(address) >= 2 and address[1] == NTP_PORT:
            ntp.reached.append(tuple(address[:2]))
            raise OSError("tests never reach a real time server (conftest.py)")
        return _REAL_SENDTO(sock, data, *args)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    if request.node.get_closest_marker("real_ntp") is None:
        monkeypatch.setattr(fast_entry, "ntp_offset", ntp)
    if hasattr(dashboard, "_clock"):
        monkeypatch.setattr(dashboard, "_clock", copy.copy(PRISTINE_CLOCK))
    yield ntp
    ntp.release()
    ntp.wait()
    assert not ntp.reached, f"a test sent a datagram to a time server's port 123: {ntp.reached}"


def pytest_sessionfinish(session):
    if not REAL_HALT_AT_START and os.path.exists(REAL_HALT):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        print(f"\nA halt.json appeared in {REAL_STATE} while the tests ran: the live bot obeys it. If a test left it, delete it.")
