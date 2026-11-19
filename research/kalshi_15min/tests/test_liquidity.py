"""liquidity.py: Kalshi's trade tape around each of the live rule's bets, and what the live bot could have bought.

`bets()` runs on the synthetic history. Everything that talks to Kalshi runs against a stand-in session and a fake
clock, so nothing here sleeps or touches the network: the pacing that keeps off the API in the live bot's entry
minutes, the retries, which endpoint a window's trades are read from, and the cursor that pages through them.
`reduce()` is checked on a tape built by hand, where what the bot could have got can be worked out from the rule.
"""

from __future__ import annotations

import json

import pytest
import requests


@pytest.fixture
def liq(study):
    """The module, imported once the synthetic history is the working directory (it reads strategies_backtest)."""
    import liquidity
    return liquidity


class Clock:
    """time.time() and time.sleep() for the module under test: sleeping moves the clock instead of waiting."""

    def __init__(self, now):
        self.now, self.slept = float(now), []

    def time(self):
        return self.now

    def sleep(self, s):
        self.slept.append(round(s, 6))
        self.now += s


class Response:
    def __init__(self, status=200, data=None):
        self.status_code, self.data = status, data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.data


class Session:
    """Answers each GET with the next item of `script`: a Response, or an exception to raise."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def api(liq, monkeypatch):
    """A fake clock (outside the live bot's entry minutes) and a hook to install a scripted session."""
    clock = Clock(1_790_000_000 - 1_790_000_000 % 900 + 100)   # 100 s into a window
    monkeypatch.setattr(liq, "time", clock)
    monkeypatch.setattr(liq, "last", [0.0])
    monkeypatch.setattr(liq.local, "s", None, raising=False)

    def install(*script):
        liq.local.s = Session(*script)
        return liq.local.s
    return clock, install


# ------------------------------------------------------------------ which bets


def test_bets_are_the_live_rules_bets_on_the_history(study, liq):
    sb = study.strategies_backtest
    live = next(s for s in sb.LIVE if s["id"] == "live")
    windows, _, _ = sb.load()
    out = liq.bets()
    assert out, "the synthetic history has favourites the live rule buys"
    jul18 = sb.ts(study.history.JUL18)
    assert min(windows) < jul18 <= min(t for _, t, _, _ in out), "the tape is fetched from Jul 18 only, though the history is longer"
    by_ticker = {m["ticker"]: (t, m) for t, ms in windows.items() for m in ms}
    for ticker, t, side, top in out:
        w, m = by_ticker[ticker]
        assert w == t and m["group"] in live["groups"]
        assert (side, top) == sb.favourite(*m["q"][live["minute"]]) and sb.LO <= top <= sb.HI
        assert not sb.skipped(live, m, side)
        assert not any(t < z and t + 900 > a for a, z in live["blackouts"])


def test_bets_skip_the_fed_windows(study, liq, monkeypatch):
    sb = study.strategies_backtest
    every = liq.bets()
    first = min(t for _, t, _, _ in every)
    live = [dict(s, blackouts=s["blackouts"] + [(first, first + 900)]) if s["id"] == "live" else s for s in sb.LIVE]
    monkeypatch.setattr(sb, "LIVE", live)
    assert [b for b in every if b[1] != first] == liq.bets()


# ------------------------------------------------------------------ pacing and retries


def test_pace_waits_out_the_live_bots_entry_minutes(liq, api):
    clock, _ = api
    clock.now = clock.now - clock.now % 900 + 500         # minute 8:20, while the live bot orders
    liq.pace()
    assert clock.now % 900 == 561 and clock.slept == [61]


def test_pace_keeps_requests_at_most_rate_a_second(liq, api):
    clock, _ = api
    liq.pace()
    liq.pace()
    assert clock.slept == [round(1 / liq.RATE, 6)]
    clock.now += 5
    liq.pace()
    assert len(clock.slept) == 1, "no wait once the gap is already longer than the rate needs"


def test_get_returns_the_json_and_keeps_one_session_a_thread(liq, api, monkeypatch):
    _, install = api
    monkeypatch.delattr(liq.local, "s")
    made = []
    monkeypatch.setattr(liq.requests, "Session", lambda: made.append(Session(Response(200, {"a": 1}))) or made[-1])
    assert liq.get("/markets/trades", {"ticker": "X"}) == {"a": 1}
    assert len(made) == 1 and made[0].calls == [(liq.BASE + "/markets/trades", {"ticker": "X"})]


def test_get_retries_network_errors_429s_and_5xx_then_answers(liq, api):
    clock, install = api
    s = install(requests.ConnectionError("down"), Response(429), Response(503), Response(200, {"ok": True}))
    assert liq.get("/p", {}) == {"ok": True}
    assert len(s.calls) == 4
    assert [x for x in clock.slept if x >= 1] == [1, 4, 6], "1 s after a dropped connection, then 2 + 2i s"


def test_get_raises_on_a_4xx_rather_than_retrying(liq, api):
    _, install = api
    s = install(Response(404))
    with pytest.raises(requests.HTTPError):
        liq.get("/p", {})
    assert len(s.calls) == 1


def test_get_gives_up_after_six_tries(liq, api):
    _, install = api
    install(*[Response(500)] * 6)
    with pytest.raises(RuntimeError, match="gave up on /p"):
        liq.get("/p", {"x": 1})


# ------------------------------------------------------------------ the tape


def trade(sec, t, side, yes_price, count, taker):
    from datetime import datetime, timezone
    when = datetime.fromtimestamp(t + sec, timezone.utc).isoformat().replace("+00:00", "Z")
    return {"created_time": when, "yes_price_dollars": f"{yes_price:.4f}", "no_price_dollars": f"{1 - yes_price:.4f}",
            "count_fp": f"{count:.2f}", "taker_side": taker}


def test_tape_pages_through_the_live_endpoint_and_keeps_our_side(liq, api):
    _, install = api
    t = liq.CUTOFF + 86400                                   # after the cutoff: /markets/trades first
    s = install(Response(200, {"trades": [trade(495, t, "yes", 0.95, 4, "yes"), trade(484, t, "yes", 0.96, 2, "no")],
                               "cursor": "next"}),
                Response(200, {"trades": [trade(483, t, "yes", 0.95, 3, "yes")], "cursor": ""}))
    got = liq.tape("KXBTC15M-X", t, "yes")
    assert got == [[483.0, 0.95, 3.0], [495.0, 0.95, 4.0]], "sorted by time, only takers who bought YES"
    assert [c[0] for c in s.calls] == [liq.BASE + "/markets/trades"] * 2
    first, second = (c[1] for c in s.calls)
    assert (first["min_ts"], first["max_ts"], "cursor" in first) == (int(t) + 470, int(t) + 600, False)
    assert second["cursor"] == "next"


def test_tape_reads_the_historical_endpoint_first_before_the_cutoff_and_prices_no_from_its_own_leg(liq, api):
    _, install = api
    t = liq.CUTOFF - 86400
    s = install(Response(200, {"trades": [trade(490, t, "yes", 0.04, 5, "no")]}))
    assert liq.tape("KXETH15M-X", t, "no") == [[490.0, 0.96, 5.0]]
    assert [c[0] for c in s.calls] == [liq.BASE + "/historical/trades"]


def test_tape_falls_back_to_the_other_endpoint_when_the_first_has_nothing(liq, api):
    _, install = api
    t = liq.CUTOFF - 300                                     # opens before the cutoff, closes after it
    s = install(Response(200, {"trades": []}), Response(200, {"trades": [trade(500, t, "yes", 0.93, 1, "yes")]}))
    assert liq.tape("KXSOL15M-X", t, "yes") == [[500.0, 0.93, 1.0]]
    assert [c[0].rsplit("/", 2)[-2] for c in s.calls] == ["markets", "historical"]


def test_tape_is_empty_when_neither_endpoint_has_a_trade(liq, api):
    _, install = api
    s = install(Response(200, {"trades": []}), Response(200, {}))
    assert liq.tape("KXSOL15M-X", liq.CUTOFF + 86400, "yes") == []
    assert len(s.calls) == 2


# ------------------------------------------------------------------ fetch and reduce


def test_fetch_resumes_and_writes_one_line_a_bet(liq, monkeypatch, tmp_path, capsys):
    path = tmp_path / "tape.jsonl"
    path.write_text(json.dumps({"t": "A", "tr": []}) + "\n")
    monkeypatch.setattr(liq, "bets", lambda: [("A", 1.0, "yes", 0.95), ("B", 2.0, "no", 0.92), ("C", 3.0, "yes", 0.97)])
    monkeypatch.setattr(liq, "tape", lambda ticker, t, side: [[490.0, 0.95, t]])
    liq.fetch(str(path))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert lines[0] == {"t": "A", "tr": []}
    assert sorted((x["t"], x["tr"][0][2]) for x in lines[1:]) == [("B", 2.0), ("C", 3.0)], "A was already done"
    assert "1 done, 2 to fetch" in capsys.readouterr().out


def test_fetch_from_scratch_reports_progress_every_thousand(liq, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(liq, "bets", lambda: [(f"T{i}", float(i), "yes", 0.95) for i in range(1000)])
    monkeypatch.setattr(liq, "tape", lambda ticker, t, side: [])
    liq.fetch(str(tmp_path / "tape.jsonl"))
    out = capsys.readouterr().out
    assert "0 done, 1000 to fetch" in out and "1000/1000" in out
    assert len((tmp_path / "tape.jsonl").read_text().splitlines()) == 1000


def test_reduce_measures_what_the_bot_could_have_got(liq, monkeypatch, tmp_path, capsys):
    S, D = liq.SEND, liq.DEPTH
    monkeypatch.setattr(liq, "bets", lambda: [("RAN", 1.0, "yes", 0.95), ("DEEP", 2.0, "yes", 0.95),
                                              ("NONE", 3.0, "no", 0.92), ("QUIET", 4.0, "yes", 0.95)])
    tape = [
        # the price ran away: the first trade after SEND is 4 s later at 96c, above our 95c
        {"t": "RAN", "tr": [[S - 5, 0.95, 9], [S + 4, 0.96, 2], [S + 20, 0.95, 1]]},
        # traders kept buying at our price: 3 + 2 within DEPTH, the 4 at 97c and the 6 past DEPTH don't count
        {"t": "DEEP", "tr": [[S + 1.5, 0.95, 3], [S + 10, 0.97, 4], [S + D, 0.94, 2], [S + D + 1, 0.95, 6]]},
        # nobody traded on our side after SEND
        {"t": "NONE", "tr": [[S - 1, 0.92, 5]]},
        # a market the live rule doesn't bet any more: left out
        {"t": "GONE", "tr": [[S + 1, 0.95, 1]]},
    ]
    path = tmp_path / "tape.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in tape))
    monkeypatch.chdir(tmp_path)
    liq.reduce(str(path))
    out = json.loads((tmp_path / "liquidity.json").read_text(encoding="utf-8"))
    assert (out["send"], out["depth"]) == (S, D)
    assert out["markets"] == {"RAN": [4.0, 0.96, 1.0], "DEEP": [1.5, 0.95, 5.0], "NONE": [None, None, 0.0]}
    assert "liquidity.json: 3 of 4 bets" in capsys.readouterr().out


def test_an_earlier_start_date_takes_in_the_bets_before_jul18(study, liq):
    jul18 = study.strategies_backtest.ts(study.history.JUL18)
    later, every = set(liq.bets()), set(liq.bets("2025-12-10"))
    assert later < every and all(t < jul18 for _, t, _, _ in every - later)


def test_fetch_and_reduce_pass_the_start_date_on(liq, monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(liq, "bets", lambda since=None: asked.append(since) or [("A", 1.0, "yes", 0.95)])
    monkeypatch.setattr(liq, "tape", lambda ticker, t, side: [])
    monkeypatch.chdir(tmp_path)
    liq.fetch(str(tmp_path / "tape.jsonl"), "2025-12-10")
    liq.reduce(str(tmp_path / "tape.jsonl"), "2025-12-10")
    liq.reduce(str(tmp_path / "tape.jsonl"))
    assert asked == ["2025-12-10", "2025-12-10", None]
