"""fast_entry.ntp_offset: how far this PC's clock is from real time, read from time servers with SNTP (the simple form
of NTP, the Network Time Protocol). The bot uses it as Kalshi's clock offset while the fast-entry experiment runs
(research/kalshi_15min/lab/fast_entry/timing.md).

Each server gets one UDP datagram, all of them at once: 48 bytes, the first 0x1B (no leap-second warning, version 3,
client mode), to port 123. Its answer gives the offset ((t1 - t0) + (t2 - t3)) / 2:
- t0 and t3 are this PC's clock when the request left and when the answer came back;
- t1 and t2 are the server's clock when it got the request and when it sent the answer. They're bytes 32-39 and 40-47
  of the reply, each as whole seconds since 1900 and then a fraction in 1/2^32ths, both big-endian.
The reading is the median over the servers that answered with a whole 48-byte reply. A server that times out, fails
(OSError) or answers short is passed over, and with no answer at all the reading is None. Every socket is closed.

The sockets and the clock are fakes handed in through sock= and clock=, so nothing here touches the network and
nothing sleeps.

    python -m pytest tests/test_fast_entry_ntp.py -q
"""
import inspect
import socket
import struct
import threading
import time

import pytest

from kalshi_bot import fast_entry

# ntp_offset's own tests get the real one, not conftest.py's fake_ntp: they hand it fake sockets themselves
pytestmark = pytest.mark.real_ntp

ERA = 2208988800         # seconds from 1900 (where NTP counts from) to 1970 (where Unix time, and time.time, does)
T0 = 1_791_777_600.0      # this PC's clock when a request leaves (Oct 2026)


def stamp(t):
    """Unix time t as an NTP timestamp: whole seconds since 1900, then the fraction in 1/2^32ths, both big-endian."""
    whole = int(t)
    frac = round((t - whole) * 2 ** 32)
    if frac == 2 ** 32:
        whole, frac = whole + 1, 0
    return struct.pack("!II", whole + ERA, frac)


def reply(t1, t2, request=bytes(48)):
    """A server's 48-byte answer: it got the request at t1 and sent this at t2, both on its own clock. Like a real
    server, it says it's in sync (stratum 2, server mode) and echoes the request's transmit time as its originate time."""
    head = bytes([0x24, 2, 6, 0xEC]) + bytes(8) + b"GOOG" + stamp(t1 - 16)   # leap 0, version 4, mode 4; stratum 2
    return head + request[40:48] + stamp(t1) + stamp(t2)


# ------------------------------------------------------------------ the fake network
def ahead(offset):
    """A server whose clock is `offset` s ahead of the PC's and that answers in no time: t1 = t2 = t0 + offset."""
    return lambda request, net: reply(net.t0 + offset, net.t0 + offset, request)


def answering(t1, t2):
    """A server that got the request at t1 and answered at t2 (its clock)."""
    return lambda request, net: reply(t1, t2, request)


def short(n):
    """A server whose reply is cut to its first n bytes."""
    return lambda request, net: reply(net.t0, net.t0, request)[:n]


def raises(e):
    """A server whose answer never comes: reading it raises e."""
    def answer(request, net):
        raise e
    return answer


class Net:
    """The servers a test can reach, and every socket ntp_offset made to reach them.

    answers: host -> what it sends back, from the four helpers above; a host not in it never answers (a timeout).
    refuse: host -> the error raised when a datagram is sent to it (a name that won't resolve, say).
    The PC's clock (clock) reads t0 until any answer has come back, and t3 after. With a barrier, each answer waits
    until that many requests are waiting for theirs at once."""

    def __init__(self, answers, refuse=None, t0=T0, t3=T0, barrier=None):
        self.answers, self.refuse = answers, refuse or {}
        self.t0, self.t3, self.barrier = t0, t3, barrier
        self.made, self.lock = [], threading.Lock()

    def socket(self, *args, **kwargs):
        s = Sock(self, args, kwargs)
        with self.lock:
            self.made.append(s)
        return s

    def clock(self):
        with self.lock:
            made = list(self.made)
        return self.t3 if any(s.answered for s in made) else self.t0


class Sock:
    """A UDP socket that never touches the network: it notes what was sent where, and answers as its Net says."""

    def __init__(self, net, args, kwargs):
        self.net, self.args, self.kwargs = net, args, kwargs
        self.timeout = self.addr = self.request = None
        self.answered = self.closed = False

    def settimeout(self, t):
        self.timeout = t

    def setblocking(self, flag):
        self.timeout = None if flag else 0.0

    def connect(self, addr):
        self.addr = addr

    def sendto(self, data, addr):
        self.addr = addr
        return self.send(data)

    def send(self, data):
        self.request = bytes(data)
        if self.addr[0] in self.net.refuse:
            raise self.net.refuse[self.addr[0]]
        return len(data)

    def sendall(self, data):
        self.send(data)

    def recvfrom(self, size):
        return self.recv(size), (self.addr[0], 123)

    def recv(self, size):
        if self.net.barrier is not None:
            self.net.barrier.wait()
        answer = self.net.answers.get(self.addr[0], raises(socket.timeout("timed out")))
        data = answer(self.request, self.net)[:size]
        self.answered = True
        return data

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def offset(hosts, net, **kw):
    return fast_entry.ntp_offset(hosts, sock=net.socket, clock=net.clock, **kw)


# ------------------------------------------------------------------ the servers and the defaults
def test_the_servers_it_asks_by_default():
    assert fast_entry.NTP_HOSTS == ("time.windows.com", "time.google.com", "time.cloudflare.com")


def test_the_defaults_are_those_servers_half_a_second_a_real_socket_and_the_pcs_clock():
    p = inspect.signature(fast_entry.ntp_offset).parameters
    assert list(p)[:4] == ["hosts", "timeout", "sock", "clock"]
    assert p["hosts"].default == fast_entry.NTP_HOSTS and p["timeout"].default == 0.5
    assert p["sock"].default is socket.socket and p["clock"].default is time.time


# ------------------------------------------------------------------ the request
def test_each_server_gets_one_48_byte_udp_request_starting_0x1b_on_port_123():
    hosts = ("a.test", "b.test", "c.test")
    net = Net({h: ahead(0.1) for h in hosts})
    offset(hosts, net, timeout=0.25)
    assert sorted(s.addr for s in net.made) == [("a.test", 123), ("b.test", 123), ("c.test", 123)]   # one each, by name
    for s in net.made:
        assert len(s.request) == 48 and s.request[0] == 0x1B
        assert socket.SOCK_DGRAM in (*s.args, *s.kwargs.values())     # UDP
        assert s.timeout == 0.25                                      # the timeout it was given, on every socket


# ------------------------------------------------------------------ the arithmetic
@pytest.mark.parametrize("t1, t2, t3, want", [
    (T0 + 0.195, T0 + 0.205, T0 + 0.090, 0.155),    # this PC 155 ms behind: 40 ms each way, 10 ms at the server
    (T0 - 0.260, T0 - 0.250, T0 + 0.090, -0.300),   # a PC 300 ms ahead
    (T0 + 3600.5, T0 + 3600.5, T0, 3600.5),         # an hour and a half-second out, answered in no time
])
def test_the_offset_is_the_average_of_the_two_one_way_differences(t1, t2, t3, want):
    """((t1 - t0) + (t2 - t3)) / 2 from a reply built by hand: in the first case using t2 alone would give 160 ms and
    t1 alone 150 ms, so both have to be read, fractions and all, from the right bytes and era."""
    net = Net({"a.test": answering(t1, t2)}, t3=t3)
    assert offset(("a.test",), net) == pytest.approx(want, abs=1e-6)


def test_the_reading_is_the_median_over_the_servers():
    net = Net({"a.test": ahead(0.10), "b.test": ahead(0.25), "c.test": ahead(0.16)})
    assert offset(("a.test", "b.test", "c.test"), net) == pytest.approx(0.16, abs=1e-6)


def test_with_two_answers_the_median_is_their_middle():
    net = Net({"a.test": ahead(0.10), "b.test": ahead(0.20)})
    assert offset(("a.test", "b.test", "c.test"), net) == pytest.approx(0.15, abs=1e-6)   # c.test never answers


# ------------------------------------------------------------------ servers that don't answer properly
def test_servers_that_time_out_fail_or_answer_short_are_passed_over():
    hosts = ("late.test", "reset.test", "down.test", "nodns.test", "short.test", "empty.test", "ok.test")
    net = Net({"reset.test": raises(ConnectionResetError(10054, "connection reset by the far end")),
               "down.test": raises(OSError("network is unreachable")),
               "short.test": short(47), "empty.test": short(0), "ok.test": ahead(0.155)},
              refuse={"nodns.test": socket.gaierror(11001, "getaddrinfo failed")})
    assert offset(hosts, net) == pytest.approx(0.155, abs=1e-6)        # late.test times out
    assert len(net.made) == len(hosts) and all(s.closed for s in net.made)


def test_with_no_answer_at_all_it_is_none():
    net = Net({"short.test": short(40)}, refuse={"nodns.test": socket.gaierror(11001, "getaddrinfo failed")})
    assert offset(("a.test", "short.test", "nodns.test"), net) is None
    assert len(net.made) == 3 and all(s.closed for s in net.made)


def test_with_no_servers_it_is_none():
    net = Net({})
    assert offset((), net) is None
    assert net.made == []


def test_every_socket_is_closed_when_every_server_answers_too():
    hosts = ("a.test", "b.test", "c.test")
    net = Net({h: ahead(0.1) for h in hosts})
    assert offset(hosts, net) == pytest.approx(0.1, abs=1e-6)
    assert len(net.made) == 3 and all(s.closed for s in net.made)


# ------------------------------------------------------------------ in parallel
def test_the_servers_are_asked_at_the_same_time():
    """Each answer waits until all three requests are out (2 s, then the barrier breaks): asked one after another, the
    first would wait for the others in vain and the reading would fail."""
    hosts = ("a.test", "b.test", "c.test")
    net = Net({h: ahead(x) for h, x in zip(hosts, (0.1, 0.2, 0.3))}, barrier=threading.Barrier(3, timeout=2))
    assert offset(hosts, net) == pytest.approx(0.2, abs=1e-6)
    assert not net.barrier.broken
    assert all(s.closed for s in net.made)
