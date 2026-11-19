"""deploy/probe_latency.py: times GETs of Kalshi's public /exchange/status on a reused connection to each prod address.

A fake session answers (or fails) on cue and a fake clock gives the times, so nothing here touches the network.

    python -m pytest tests/test_probe_latency.py -q
"""
import runpy
import sys
import time

import pytest
import requests

from layout import DEPLOY

sys.path.insert(0, DEPLOY)
import probe_latency as pl  # noqa: E402


class Session:
    """A stand-in for requests.Session: records each GET, answers each with the next status or raises the next error."""
    made = []

    def __init__(self, answers=None):
        self.answers, self.calls, self.closed = list(answers or []), [], False
        Session.made.append(self)

    def get(self, url, **kw):
        self.calls.append((url, kw))
        a = self.answers.pop(0) if self.answers else 200
        if isinstance(a, Exception):
            raise a
        return type("Answer", (), {"status_code": a})()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True


def clock(*seconds):
    it = iter(seconds)
    return lambda: next(it)


@pytest.fixture(autouse=True)
def fresh():
    Session.made = []


def test_it_probes_both_prod_addresses_recommended_first():
    assert pl.HOSTS == ("https://external-api.kalshi.com/trade-api/v2", "https://api.elections.kalshi.com/trade-api/v2")
    assert pl.PATH == "/exchange/status" and pl.TIMEOUT == 10


def test_each_request_is_timed_on_the_one_session_with_no_key():
    s, naps = Session(), []
    out = pl.probe(pl.HOSTS[0], 3, s, clock=clock(0.0, 0.050, 1.0, 1.002, 2.0, 2.0015), sleep=naps.append)
    assert [round(ms, 3) for ms, _ in out] == [50.0, 2.0, 1.5] and [st for _, st in out] == [200, 200, 200]
    assert s.calls == [("https://external-api.kalshi.com/trade-api/v2/exchange/status", {"timeout": 10})] * 3  # no headers
    assert naps == [pl.GAP, pl.GAP]                    # a pause between requests, none before the first


def test_a_failed_request_has_no_time_and_says_what_went_wrong():
    s = Session([requests.ConnectionError("down"), 429])
    out = pl.probe(pl.HOSTS[1], 2, s, clock=clock(0.0, 1.0, 1.003), sleep=lambda _: None)
    assert out[0] == (None, "ConnectionError") and out[1][1] == 429 and round(out[1][0], 3) == 3.0


def test_nearest_rank_percentiles():
    assert pl.nearest_rank(list(range(1, 20)), 0.9) == 18
    assert pl.nearest_rank([5.0], 0.9) == 5.0
    assert pl.nearest_rank([3, 1, 2], 1.0) == 3


def test_the_summary_keeps_the_cold_request_apart():
    out = [(80.0, 200)] + [(float(ms), 200) for ms in range(1, 11)]
    assert pl.summary(pl.HOSTS[0], out) == (
        "external-api.kalshi.com    cold 80.0 ms · warm (10): median 5.5, p90 9.0, max 10.0 ms")


def test_the_summary_counts_what_wasnt_a_200():
    out = [(None, "ConnectTimeout"), (2.0, 200), (3.0, 429), (None, "ConnectionError"), (4.0, 429)]
    assert pl.summary(pl.HOSTS[1], out) == (
        "api.elections.kalshi.com   cold failed · warm (3): median 3.0, p90 4.0, max 4.0 ms"
        " · not 200: ConnectTimeout x1, 429 x2, ConnectionError x1")


def test_the_summary_with_nothing_warm():
    assert pl.summary(pl.HOSTS[0], [(40.0, 200)]).endswith("cold 40.0 ms · no warm answers")


def test_main_probes_each_address_on_a_session_of_its_own(capsys):
    assert pl.main(["-n", "2"], session=Session, clock=clock(*[0.0, 0.001] * 4), sleep=lambda _: None) == 0
    assert [c[0] for s in Session.made for c in s.calls] == [pl.HOSTS[0] + pl.PATH] * 2 + [pl.HOSTS[1] + pl.PATH] * 2
    assert all(s.closed for s in Session.made) and len(Session.made) == 2
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("2 GETs of /exchange/status to each address")
    assert lines[1].startswith("external-api.kalshi.com ") and lines[2].startswith("api.elections.kalshi.com ")


def test_main_defaults_to_20_requests_and_refuses_fewer_than_1(capsys):
    assert pl.main([], session=Session, clock=clock(*[0.0, 0.001] * 40), sleep=lambda _: None) == 0
    assert [len(s.calls) for s in Session.made] == [20, 20]
    with pytest.raises(SystemExit) as e:
        pl.main(["-n", "0"], session=Session)
    assert e.value.code == 2


def test_by_default_it_uses_a_real_session_clock_and_sleep():
    import inspect
    p = inspect.signature(pl.main).parameters
    assert p["session"].default is requests.Session and p["clock"].default is time.perf_counter
    assert p["sleep"].default is time.sleep


def test_run_as_a_script(monkeypatch, capsys):
    monkeypatch.setattr(requests, "Session", Session)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["probe_latency.py", "-n", "1"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(pl.__file__, run_name="__main__")
    assert e.value.code == 0 and len(Session.made) == 2 and "no warm answers" in capsys.readouterr().out
