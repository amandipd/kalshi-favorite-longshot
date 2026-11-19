"""The research's data fetchers against a fake Kalshi: backtest_large.py (the shared HTTP helper), fetch_minutes.py,
fetch_all15.py, fetch_history.py, fetch_other.py and fetch_quotes.py.

Every request goes to an in-memory fake through each module's own `get`, so nothing touches the network, and every
test runs in its own temporary folder, so the files the fetchers write never land in the shared synthetic history.
What is checked is what a long fetch leans on: retries, paging, carrying a quote forward over a quiet minute, and
resuming without fetching anything twice.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

UTC = timezone.utc
OPEN = "2026-09-01T12:00:00Z"
OPEN_TS = int(datetime(2026, 9, 1, 12, tzinfo=UTC).timestamp())


def candle(minute, price=None, bid=None, ask=None, key="close_dollars", volume=None):
    c = {"end_period_ts": OPEN_TS + 60 * minute}
    for name, v in (("price", price), ("yes_bid", bid), ("yes_ask", ask)):
        c[name] = {} if v is None else {key: str(v)}
    if volume is not None:
        c["volume_fp"] = str(volume)
    return c


@pytest.fixture()
def here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ------------------------------------------------------------------ backtest_large: the shared helper


class Reply:
    def __init__(self, status, body=None):
        self.status_code, self.body = status, body

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class Script:
    """A session that answers from a list, recording each call."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture()
def bl(study, monkeypatch):
    m = study.backtest_large
    monkeypatch.setattr(m, "limiter", m.RateLimiter(1e9))
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


def test_get_retries_rate_limits_server_errors_and_network_errors(bl, monkeypatch):
    s = Script(Reply(429), Reply(503), requests.ConnectionError("reset"), Reply(200, {"ok": 1}))
    monkeypatch.setattr(bl, "session", lambda: s)
    assert bl.get("u", {"a": 1}) == {"ok": 1} and len(s.calls) == 4


def test_get_gives_up_with_none_and_raises_on_a_refusal(bl, monkeypatch):
    monkeypatch.setattr(bl, "session", lambda: Script(*[Reply(500)] * 5))
    assert bl.get("u") is None
    monkeypatch.setattr(bl, "session", lambda: Script(Reply(404)))
    with pytest.raises(requests.HTTPError):
        bl.get("u")


def test_the_rate_limiter_spaces_calls(study, monkeypatch):
    m = study.backtest_large
    clock, slept = {"t": 0.0}, []
    monkeypatch.setattr(m.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(m.time, "sleep", lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)))
    limiter = m.RateLimiter(10)
    limiter.acquire()
    limiter.acquire()
    assert slept == [pytest.approx(0.1)]


def test_one_session_per_thread(study):
    import threading
    m = study.backtest_large
    mine = m.session()
    assert m.session() is mine
    other = []
    t = threading.Thread(target=lambda: other.append(m.session()))
    t.start()
    t.join()
    assert other[0] is not mine


def test_fetch_settled_markets_pages_until_it_has_enough(bl, monkeypatch):
    pages = {None: {"markets": [{"ticker": "A"}, {"ticker": "B"}], "cursor": "c2"},
             "c2": {"markets": [{"ticker": "C"}], "cursor": ""}}
    monkeypatch.setattr(bl, "get", lambda url, params=None: pages[params.get("cursor")])
    assert [m["ticker"] for m in bl.fetch_settled_markets("S", 10)] == ["A", "B", "C"]
    assert [m["ticker"] for m in bl.fetch_settled_markets("S", 1)] == ["A"]
    monkeypatch.setattr(bl, "get", lambda url, params=None: None)
    assert bl.fetch_settled_markets("S", 10) == []


def test_snapshot_reads_the_minute_8_candle(bl, monkeypatch):
    market = {"ticker": "T", "open_time": OPEN, "result": "yes"}
    candles = {"candlesticks": [candle(7, price=0.6), candle(8, price=0.7, volume=12)]}
    monkeypatch.setattr(bl, "get", lambda url, params=None: candles)
    snap = bl.snapshot("S", market)
    assert snap == {"series": "S", "ticker": "T", "open_time": OPEN, "price_8min": 0.7, "volume_8min": 12.0,
                    "resolved_yes": 1}
    assert bl.snapshot("S", {**market, "result": ""}) is None
    monkeypatch.setattr(bl, "get", lambda url, params=None: {"candlesticks": [candle(6, price=0.4)]})
    assert bl.snapshot("S", market)["price_8min"] == 0.4          # no minute-8 candle: the last one
    monkeypatch.setattr(bl, "get", lambda url, params=None: {"candlesticks": [candle(8)]})
    assert bl.snapshot("S", market) is None                         # no trade at all
    monkeypatch.setattr(bl, "get", lambda url, params=None: {"candlesticks": []})
    assert bl.snapshot("S", market) is None


def test_backtest_large_main_writes_the_snapshots(bl, here, monkeypatch, capsys):
    monkeypatch.setattr(bl, "SERIES", ["KXBTC15M", "KXGOLD15M"])
    monkeypatch.setattr(bl, "fetch_settled_markets", lambda s, n: [{"ticker": f"{s}-1"}, {"ticker": f"{s}-2"}])
    monkeypatch.setattr(bl, "snapshot", lambda s, m: None if m["ticker"].endswith("2") else
                        {"series": s, "ticker": m["ticker"], "open_time": OPEN, "price_8min": 0.5, "volume_8min": 0.0,
                         "resolved_yes": 1})
    bl.main()
    with open("snapshots_8min.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["ticker"] for r in sorted(rows, key=lambda r: r["ticker"])] == ["KXBTC15M-1", "KXGOLD15M-1"]
    assert "Wrote 2 snapshots" in capsys.readouterr().out


# ------------------------------------------------------------------ fetch_minutes


def test_close_falls_back_to_the_previous_value(study):
    close = study.fetch_minutes.close
    assert close({"close_dollars": "0.5"}) == 0.5 and close({"previous_dollars": "0.4"}) == 0.4
    assert close(None) is None and close({}) is None


def test_fetch_window_carries_each_quote_forward(study, monkeypatch):
    fm = study.fetch_minutes
    body = {"markets": [{"market_ticker": "A", "candlesticks": [candle(2, 0.6, 0.59, 0.61), candle(5, 0.9, 0.89, 0.91)]},
                        {"market_ticker": "B", "candlesticks": []}]}
    monkeypatch.setattr(fm, "get", lambda url, params=None: body)
    markets = [{"ticker": t, "series": "S", "resolved_yes": "1"} for t in ("A", "B")]
    (row,) = fm.fetch_window(OPEN, markets)
    assert row["ticker"] == "A" and row["p1"] == "" and row["p2"] == row["p4"] == 0.6 and row["a15"] == 0.91
    assert set(row) == set(fm.FIELDS)
    monkeypatch.setattr(fm, "get", lambda url, params=None: None)
    assert fm.fetch_window(OPEN, markets) == []


def test_fetch_minutes_main_resumes_by_window(study, here, monkeypatch, capsys):
    fm = study.fetch_minutes
    with open("snapshots_30d.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["series", "ticker", "open_time", "price_8min", "resolved_yes"])
        w.writeheader()
        w.writerow({"series": "S", "ticker": "A", "open_time": OPEN, "price_8min": 0.5, "resolved_yes": "1"})
        w.writerow({"series": "S", "ticker": "B", "open_time": "2026-09-01T12:15:00Z", "price_8min": 0.5, "resolved_yes": "0"})
    asked = []

    def get(url, params=None):
        asked.append(params["start_ts"])
        o = params["start_ts"]
        return {"markets": [{"market_ticker": t, "candlesticks": [{"end_period_ts": o + 60, "price": {"close_dollars": "0.5"},
                                                                  "yes_bid": {}, "yes_ask": {}}]}
                            for t in params["market_tickers"].split(",")]}

    monkeypatch.setattr(fm, "get", get)
    fm.main()
    fm.main()
    with open("minutes_30d.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(r["ticker"] for r in rows) == ["A", "B"] and len(asked) == 2, "the rerun fetched nothing"
    assert "2 already saved, fetching 0" in capsys.readouterr().out


# ------------------------------------------------------------------ fetch_all15 and fetch_history


def test_all_markets_follows_the_cursor(study, monkeypatch):
    fa = study.fetch_all15
    pages = {None: {"markets": [{"ticker": "A"}], "cursor": "x"}, "x": {"markets": [{"ticker": "B"}], "cursor": None}}
    monkeypatch.setattr(fa, "get", lambda url, params=None: pages[params.get("cursor")])
    assert [m["ticker"] for m in fa.all_markets("S")] == ["A", "B"]
    monkeypatch.setattr(fa, "get", lambda url, params=None: None)
    assert fa.all_markets("S") == []


def test_fetch_all15_main_writes_the_universe_and_the_new_series(study, here, monkeypatch, capsys):
    fa = study.fetch_all15
    catalog = {"series": [
        {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto", "fee_multiplier": 1},
        {"ticker": "KXEURUSD15M", "frequency": "fifteen_min", "category": "Financials", "fee_multiplier": 1},
        {"ticker": "KXSPX15M", "frequency": "fifteen_min", "category": "Financials"},
        {"ticker": "KXBTC15MTEST", "frequency": "fifteen_min", "category": "Crypto"},
        {"ticker": "KXBTCD", "frequency": "hourly", "category": "Crypto"}]}
    markets = {"KXBTC15M": [{"ticker": "B1", "open_time": OPEN, "result": "yes", "status": "active"}],
               "KXEURUSD15M": [{"ticker": "E1", "open_time": OPEN, "result": "no", "status": "settled"},
                               {"ticker": "E2", "open_time": OPEN, "result": "", "status": "settled"}],
               "KXSPX15M": []}

    def get(url, params=None):
        return catalog if url.endswith("/series") else {"markets": markets[params["series_ticker"]], "cursor": None}

    monkeypatch.setattr(fa, "get", get)
    monkeypatch.setattr(fa, "fetch_window", lambda o, ms: [{"series": m["series"], "ticker": m["ticker"], "open_time": o,
                                                           "resolved_yes": m["resolved_yes"]} for m in ms])
    fa.main()
    universe = {u["ticker"]: u for u in json.load(open("universe.json", encoding="utf-8"))["series"]}
    assert set(universe) == {"KXBTC15M", "KXEURUSD15M", "KXSPX15M"}
    assert (universe["KXBTC15M"]["status"], universe["KXBTC15M"]["inOriginal"]) == ("live", True)
    assert (universe["KXEURUSD15M"]["status"], universe["KXEURUSD15M"]["group"]) == ("paused", "fx")
    assert universe["KXSPX15M"]["status"] == "not launched"
    with open("minutes_new.csv") as fh:
        assert [r["ticker"] for r in csv.DictReader(fh)] == ["E1"]   # outside the original 16, settled


def test_fetch_history_fetches_only_what_no_file_has(study, here, monkeypatch, capsys):
    fh_mod = study.fetch_history
    json.dump({"series": [{"ticker": "KXBTC15M", "markets": 3}, {"ticker": "KXNEW15M", "markets": 0}]},
              open("universe.json", "w", encoding="utf-8"))
    with open("minutes_30d.csv", "w", newline="") as f:
        f.write("ticker\nHAVE\n")
    listing = [{"ticker": "HAVE", "open_time": OPEN, "result": "yes"},
               {"ticker": "NEW", "open_time": OPEN, "result": "no"},
               {"ticker": "OPEN", "open_time": OPEN, "result": ""},
               {"ticker": "EARLY", "open_time": "2026-07-01T00:00:00Z", "result": "yes"}]
    listed = []
    monkeypatch.setattr(fh_mod, "all_markets", lambda s: listed.append(s) or listing)
    monkeypatch.setattr(fh_mod, "fetch_window", lambda o, ms: [{"series": m["series"], "ticker": m["ticker"],
                                                               "open_time": o, "resolved_yes": m["resolved_yes"]} for m in ms])
    fh_mod.main()
    assert listed == ["KXBTC15M"], "a series with no markets is not listed"
    with open("minutes_ext.csv") as fh:
        assert [r["ticker"] for r in csv.DictReader(fh)] == ["NEW"]
    assert fh_mod.saved_tickers() == {"HAVE", "NEW"}


# ------------------------------------------------------------------ fetch_other


def test_fetch_other_close_reads_a_number_a_block_or_nothing(study):
    close = study.fetch_other.close
    assert close(None) is None and close("0.4") == 0.4
    assert close({"close_dollars": "0.6"}) == 0.6 and close({"close_dollars": None}) is None
    assert close({"close": "0.93"}) == 0.93, "historical candles call it close"
    assert close({"close": None, "previous": "0.5"}) is None


def test_fetch_other_get_waits_out_the_bots_entry_paces_and_reads_a_404_as_nothing(study, monkeypatch):
    fo = study.fetch_other
    now, calls = [900 * 1000 + 500.0], []   # 8:20 into a quarter hour: the live bot is ordering

    def sleep(s):
        now[0] += s

    def base_get(url, params=None):
        calls.append(now[0] % 900)
        if url.endswith("/gone"):
            raise requests.HTTPError("404", response=SimpleNamespace(status_code=404))
        if url.endswith("/bad"):
            raise requests.HTTPError("400", response=SimpleNamespace(status_code=400))
        return {"ok": url}

    monkeypatch.setattr(fo, "time", SimpleNamespace(time=lambda: now[0], sleep=sleep))
    monkeypatch.setattr(fo, "_next", [0.0])
    monkeypatch.setattr(study.backtest_large, "get", base_get)
    assert fo.get("u/a") == {"ok": "u/a"}
    assert calls[0] > fo.QUIET[1], "nothing goes out while the live bot orders"
    assert fo.get("u/b") == {"ok": "u/b"}
    assert calls[1] - calls[0] >= 1 / fo.RATE - 1e-9, "at most RATE requests a second"
    assert fo.get("u/gone") is None, "a 404 is a market the store doesn't hold"
    with pytest.raises(requests.HTTPError):
        fo.get("u/bad")


def test_fetch_other_fetch_old_reads_the_historical_store_then_the_live_one(study, monkeypatch):
    fo = study.fetch_other
    close_ts = fo.ts("2026-08-01T13:00:00Z")
    m = {"ticker": "H1", "series": "KXBTCD", "event": "E", "close": "2026-08-01T13:00:00Z", "result": "no", "volume": 5,
         "frequency": "hourly"}
    calls = []

    def get(url, params=None):
        calls.append((url, params))
        return {"ticker": "H1", "candlesticks": [{"end_period_ts": close_ts - 120, "yes_bid": {"close": "0.03"},
                                                  "yes_ask": {"close": "0.05"}}]}

    monkeypatch.setattr(fo, "get", get)
    (row,) = fo.fetch_old(m)
    (url, params), = calls
    assert url.endswith("/historical/markets/H1/candlesticks")
    assert params == {"start_ts": close_ts - 61 * 60, "end_ts": close_ts, "period_interval": 1}
    assert (row["b2"], row["a2"], row["b0"], row["a0"]) == (0.03, 0.05, 0.03, 0.05) and row["b3"] == ""
    # closed before the cutoff but settled after it: the historical store doesn't hold it, the live endpoint does
    live = {"markets": [{"market_ticker": "H1", "candlesticks": [{"end_period_ts": close_ts, "yes_bid": {"close_dollars": "0.9"},
                                                                  "yes_ask": {"close_dollars": "0.92"}}]}]}
    urls = []
    monkeypatch.setattr(fo, "get", lambda url, params=None: urls.append(url) or (None if "/historical/" in url else live))
    (row,) = fo.fetch_old(dict(m, frequency="daily"))
    assert row["unit"] == "hour" and (row["b0"], row["a0"]) == (0.9, 0.92)
    assert ["/historical/" in u for u in urls] == [True, False]
    monkeypatch.setattr(fo, "get", lambda url, params=None: None)
    assert fo.fetch_old(m) == [] and fo.cutoff() == 0, "nothing anywhere; an unreadable cutoff sends everything to the batches"


def test_fetch_other_candles_send_markets_before_the_cutoff_to_the_historical_store(study, here, monkeypatch, capsys):
    fo = study.fetch_other
    closes = {"OLD-0": "2026-08-01T13:00:00Z", "OLD-1": "2026-08-02T13:00:00Z",
              "NEW-0": "2026-09-01T13:00:00Z", "NEW-1": "2026-09-01T13:20:00Z"}
    json.dump([{"series": "KXBTCD", "frequency": "hourly", "markets": [
        {"ticker": t, "event": "E", "open": "o", "close": c, "result": "yes", "volume": "5"} for t, c in closes.items()]}],
        open(fo.MARKETS, "w"))
    batches, single = [], []

    def get(url, params=None):
        if url.endswith("/historical/cutoff"):
            return {"market_settled_ts": "2026-08-12T00:00:00Z"}
        if "/historical/markets/" in url:
            t = url.split("/")[-2]
            single.append(t)
            return {"candlesticks": [{"end_period_ts": fo.ts(closes[t]), "yes_bid": {"close": "0.9"}, "yes_ask": {"close": "0.92"}}]}
        tickers = params["market_tickers"].split(",")
        batches.append(tickers)
        return {"markets": [{"market_ticker": t, "candlesticks": [{"end_period_ts": fo.ts(closes[t]), "yes_bid": {"close_dollars": "0.9"},
                                                                   "yes_ask": {"close_dollars": "0.92"}}]} for t in tickers]}

    monkeypatch.setattr(fo, "get", get)
    fo.candles()
    assert batches == [["NEW-0", "NEW-1"]], "markets settled after the cutoff go in batches"
    assert sorted(single) == ["OLD-0", "OLD-1"], "markets before it, one at a time from the historical store"
    with open(fo.HOURS_CSV) as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(r["ticker"] for r in rows) == sorted(closes) and {(r["b0"], r["a0"]) for r in rows} == {("0.9", "0.92")}
    assert "1 batched requests and 2 historical" in capsys.readouterr().out
    fo.candles()
    assert len(batches) == 1 and len(single) == 2, "a second run fetches nothing again"
    assert "0 markets to fetch" in capsys.readouterr().out


def test_settled_lists_a_series_whole_or_a_day_at_a_time_and_dedupes(study, monkeypatch):
    fo = study.fetch_other
    calls = []

    def get(url, params=None):
        calls.append(params)
        if params.get("cursor"):
            return {"markets": [{"ticker": "B", "close_time": "x", "result": "no", "volume_fp": "3"}], "cursor": None}
        return {"markets": [{"ticker": "A", "event_ticker": "E", "open_time": "o", "close_time": "c", "result": "yes",
                             "volume": 7}], "cursor": "next"}

    monkeypatch.setattr(fo, "get", get)
    whole = fo.settled("S")
    assert {m["ticker"] for m in whole} == {"A", "B"} and len(calls) == 2
    calls.clear()
    by_day = fo.settled("S", fo.DAY)
    assert {m["ticker"] for m in by_day} == {"A", "B"}, "the same market listed every day is kept once"
    days = (fo.ts(fo.UNTIL) - fo.ts(fo.SINCE)) // fo.DAY
    assert len(calls) == 2 * days


def test_fetch_other_fetch_counts_back_from_the_close(study, monkeypatch):
    fo = study.fetch_other
    close_ts = fo.ts("2026-09-01T13:00:00Z")
    batch = [{"ticker": "H1", "series": "KXBTCD", "event": "E", "close": "2026-09-01T13:00:00Z", "result": "yes",
              "volume": 5, "frequency": "hourly"}]
    body = {"markets": [{"market_ticker": "H1", "candlesticks": [
        {"end_period_ts": close_ts, "yes_bid": {"close_dollars": "0.95"}, "yes_ask": {"close_dollars": "0.97"}},
        {"end_period_ts": close_ts - 600, "yes_bid": {"close_dollars": "0.90"}, "yes_ask": {"close_dollars": None}}]}]}
    monkeypatch.setattr(fo, "get", lambda url, params=None: body)
    (row,) = fo.fetch(batch)
    assert row["unit"] == "min" and (row["b0"], row["a0"]) == (0.95, 0.97)
    assert (row["b10"], row["a10"]) == (0.90, "") and (row["b9"], row["a9"]) == (0.90, "")   # carried towards the close
    assert row["b60"] == "" and row["b11"] == ""
    monkeypatch.setattr(fo, "get", lambda url, params=None: None)
    assert fo.fetch(batch) == []


def test_fetch_other_lists_then_fetches_candles_resumably(study, here, monkeypatch, capsys):
    fo = study.fetch_other
    catalog = [{"ticker": "KXBTCD", "frequency": "hourly", "category": "Crypto", "title": "t", "fee_multiplier": 1},
               {"ticker": "KXBIG", "frequency": "daily", "category": "Climate"},
               {"ticker": "KX15", "frequency": "fifteen_min", "category": "Crypto"}]

    def get(url, params=None):
        if url.endswith("/series"):
            return {"series": catalog}
        if url.endswith("/historical/cutoff"):
            return {"market_settled_ts": "2026-08-12T00:00:00Z"}   # before every market here: all batched
        if url.endswith("/markets"):
            n = 1000 if params["series_ticker"] == "KXBIG" and "cursor" not in params else 1
            return {"markets": [{"ticker": f"{params['series_ticker']}-{i}", "close_time": "2026-09-01T13:00:00Z",
                                 "result": "yes", "volume_fp": "5"} for i in range(n)], "cursor": None}
        tickers = params["market_tickers"].split(",")
        return {"markets": [{"market_ticker": t, "candlesticks": [{"end_period_ts": fo.ts("2026-09-01T13:00:00Z"),
                                                                    "yes_bid": {"close_dollars": "0.9"},
                                                                    "yes_ask": {"close_dollars": "0.92"}}]} for t in tickers]}

    monkeypatch.setattr(fo, "get", get)
    monkeypatch.setattr(fo, "settled", lambda s, step=None: [
        {"ticker": f"{s}-{i}", "event": "E", "open": "o", "close": "2026-09-01T13:00:00Z", "result": "yes", "volume": "5"}
        for i in range(1000 if s == "KXBIG" and step is None else 2)])
    fo.list_markets()
    series = {s["series"]: s for s in json.load(open(fo.MARKETS))}
    assert set(series) == {"KXBTCD", "KXBIG"}, "15-minute series are not 'other' markets"
    assert len(series["KXBIG"]["markets"]) == 2, "a listing that stopped on a round thousand is re-listed by day"
    assert json.load(open("series_catalog.json")) == catalog
    fo.candles()
    fo.candles()
    with open(fo.HOURS_CSV) as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(r["ticker"] for r in rows) == ["KXBIG-0", "KXBIG-1", "KXBTCD-0", "KXBTCD-1"]
    assert "0 markets to fetch" in capsys.readouterr().out


# ------------------------------------------------------------------ fetch_quotes


def test_quote_reads_the_minute_8_book_and_liquidity(study, monkeypatch):
    fq = study.fetch_quotes
    assert fq.val({"close_dollars": "0.5"}) == 0.5 and fq.val(None) == ""
    cs = [candle(6, 0.9, 0.89, 0.91, volume=4), candle(7, 0.92, 0.91, 0.93, volume=0), candle(8, 0.95, 0.94, 0.96, volume=0)]
    for c in cs:
        c["open_interest_fp"] = "100"
    monkeypatch.setattr(fq, "get", lambda url, params=None: {"candlesticks": list(reversed(cs))})
    q = fq.quote({"series": "S", "ticker": "T", "open_time": OPEN, "price_8min": "0.95", "resolved_yes": "1"})
    assert (q["yes_bid"], q["yes_ask"], q["price_7"]) == (0.94, 0.96, 0.92)
    assert (q["vol_0_8"], q["vol_min8"], q["mins_since_trade"], q["oi_8"]) == (4.0, 0.0, 2, 100.0)
    monkeypatch.setattr(fq, "get", lambda url, params=None: {"candlesticks": []})
    assert fq.quote({"series": "S", "ticker": "T", "open_time": OPEN}) is None


def test_fetch_quotes_main_takes_85c_favourites_and_resumes(study, here, monkeypatch, capsys):
    fq = study.fetch_quotes
    with open("snapshots_30d.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["series", "ticker", "open_time", "price_8min", "resolved_yes"])
        w.writeheader()
        for t, p in (("FAV", 0.9), ("LONG", 0.1), ("COIN", 0.5)):
            w.writerow({"series": "S", "ticker": t, "open_time": OPEN, "price_8min": p, "resolved_yes": "1"})
    monkeypatch.setattr(fq, "quote", lambda r: {**{f: "" for f in fq.FIELDS}, "ticker": r["ticker"]})
    fq.main()
    fq.main()
    with open("quotes_30d.csv") as fh:
        assert sorted(r["ticker"] for r in csv.DictReader(fh)) == ["FAV", "LONG"]
    assert "2 already saved, fetching 0 more" in capsys.readouterr().out
