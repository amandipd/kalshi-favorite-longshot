"""fetch_skipped.py: the minute history for the 15-minute series the bot skips, against a fake Kalshi.

The fetch is long, so what matters is that it asks once per window (batching every series' market for
that window into one candlesticks call), keeps each call under Kalshi's ticker cap, and resumes without
fetching a window twice. Nothing here touches the network.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parent.parent
for path in (RESEARCH, RESEARCH.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

UTC = timezone.utc
START = datetime(2026, 10, 1, 12, tzinfo=UTC)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def scan(folder, series, windows, per_window=1):
    """skipped_scan.json plus the markets the fake exchange will answer for."""
    rows = [{"ticker": s, "group": "fx", "settled": windows * per_window} for s in series]
    (folder / "skipped_scan.json").write_text(json.dumps(rows), encoding="utf-8")
    markets = []
    for s in series:
        for n in range(windows):
            opened = START + timedelta(minutes=15 * n)
            for k in range(per_window):
                markets.append({"ticker": f"{s}-{n:03d}-{k}", "series": s, "open_time": iso(opened),
                                "result": "yes" if (n + k) % 2 else "no"})
    return markets


class Fake:
    """Answers /markets by series and /markets/candlesticks for any ticker, recording every call."""

    def __init__(self, markets):
        self.markets, self.calls = markets, []

    def get(self, path, params=None):
        params = params or {}
        self.calls.append((path, params))
        if path.endswith("/markets"):
            return {"markets": [m for m in self.markets if m["series"] == params["series_ticker"]], "cursor": None}
        tickers = params["market_tickers"].split(",")
        start = int(params["start_ts"])
        return {"markets": [{"market_ticker": t, "candlesticks": [
            {"end_period_ts": start + 60 * k, "price": {"close_dollars": "0.95"},
             "yes_bid": {"close_dollars": "0.94"}, "yes_ask": {"close_dollars": "0.95"}} for k in range(1, 16)]}
            for t in tickers]}

    def candle_calls(self):
        return [p for path, p in self.calls if "candlesticks" in path]


@pytest.fixture()
def here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def mod(here, monkeypatch):
    import importlib
    import fetch_skipped
    fetch_skipped = importlib.reload(fetch_skipped)
    return fetch_skipped


def run(mod, fake, monkeypatch):
    monkeypatch.setattr(mod, "get", lambda path, params=None: fake.get(path, params))
    import fetch_minutes
    monkeypatch.setattr(fetch_minutes, "get", lambda path, params=None: fake.get(path, params))
    mod.main()


def rows(folder):
    with open(folder / "minutes_skipped.csv") as fh:
        return list(csv.DictReader(fh))


def test_one_call_per_window_covers_every_series(mod, here, monkeypatch):
    """Three series over four windows: four candlesticks calls, each carrying all three tickers."""
    fake = Fake(scan(here, ["KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M"], windows=4))
    run(mod, fake, monkeypatch)
    calls = fake.candle_calls()
    assert len(calls) == 4
    assert all(len(c["market_tickers"].split(",")) == 3 for c in calls)
    assert len(rows(here)) == 12


def test_a_crowded_window_splits_into_capped_calls(mod, here, monkeypatch):
    """Kalshi caps the tickers a candlesticks call takes, so a wide window goes in several."""
    series = [f"KX{n}15M" for n in range(mod.TICKERS_PER_CALL + 3)]
    fake = Fake(scan(here, series, windows=1))
    run(mod, fake, monkeypatch)
    calls = fake.candle_calls()
    assert len(calls) == 2
    assert max(len(c["market_tickers"].split(",")) for c in calls) <= mod.TICKERS_PER_CALL
    assert len(rows(here)) == len(series)


def test_a_rerun_fetches_nothing_twice(mod, here, monkeypatch):
    fake = Fake(scan(here, ["KXEURUSD15M"], windows=3))
    run(mod, fake, monkeypatch)
    assert len(fake.candle_calls()) == 3
    again = Fake(scan(here, ["KXEURUSD15M"], windows=3))
    run(mod, again, monkeypatch)
    assert again.candle_calls() == []
    assert len(rows(here)) == 3


def test_it_records_the_settlement_and_the_quotes(mod, here, monkeypatch):
    fake = Fake(scan(here, ["KXEURUSD15M"], windows=1))
    run(mod, fake, monkeypatch)
    r = rows(here)[0]
    assert r["series"] == "KXEURUSD15M" and r["resolved_yes"] in ("0", "1")
    assert float(r["a8"]) == 0.95 and float(r["b8"]) == 0.94


def test_the_scan_file_may_carry_its_fetch_time(mod, here, monkeypatch):
    """scan_skipped.py writes {"fetched", "series"}; a bare list of rows reads the same."""
    fake = Fake(scan(here, ["KXEURUSD15M"], windows=2))
    rows_json = json.loads((here / "skipped_scan.json").read_text())
    (here / "skipped_scan.json").write_text(json.dumps({"fetched": "2026-10-25T00:00:00Z", "series": rows_json}),
                                            encoding="utf-8")
    run(mod, fake, monkeypatch)
    assert len(rows(here)) == 2


def test_series_with_nothing_settled_are_left_out(mod, here, monkeypatch):
    rows_json = [{"ticker": "KXINX15M", "group": "stock index", "settled": 0}]
    (here / "skipped_scan.json").write_text(json.dumps(rows_json), encoding="utf-8")
    fake = Fake([])
    run(mod, fake, monkeypatch)
    assert fake.calls == []
