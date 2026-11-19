"""venue_books.py: a week of order books on Gemini Predictions and Polymarket US, and its report.

The bot buys Kalshi's 15-minute crypto favourites at 90-99c around minute 8 and holds them to settlement. Two other
US-legal venues list short crypto markets with a public API: Gemini Predictions (5-minute, 15-minute and hourly on
BTC, ETH, SOL and XRP) and Polymarket US (BTC Up/Down, 15-minute and 1-hour). venue_books.py records their public
books for a week, then reports their depth at 90-99c and whether those favourites win more often than their price
says.

Everything here is offline: the venues are faked (venue_books.get monkeypatched, or requests' Session.request under
get() itself), the clock and sleep are injected, an autouse guard makes any real socket connection fail the test, and
every test runs in its own tmp_path, so OUT, RESULTS, LOG and the report land there and never in research/.

Readings of the spec (the contract where it leaves a choice):

- `get(base, path, params)` sends GET base + path through requests (requests.get or a Session: both end in
  Session.request, which the tests fake) with a `timeout`, and waits with time.sleep. TRIES counts every try, the
  first included: TRIES requests, then it raises. Each wait before a retry is longer than the one before. Headers come
  back as requests' own case-insensitive mapping.
- `iso` writes whole seconds; `epoch` reads a string without "Z" as UTC too.
- `gemini_markets`: the event's `status` must be "active" and the contract's `marketState` "open" (a contract's own
  `status` isn't pinned). `strike` is None when its value, or the whole strike, is missing. Each market dict holds
  exactly the seven keys. Order isn't pinned.
- `pmus_markets`: the slug regex is anchored and wants a "-" after the family ("15min" is out).
- `listing(now)`: Gemini is asked with category=crypto, limit=100 and offset; Polymarket US with active="true" and
  closed="false" (strings, as in the URL), limit=200, offset, endDateMin and endDateMax. The query may sit in params or
  in the path. Markets that haven't started yet are listed. A venue that fails is logged (to LOG or printed) naming the
  venue, and the other venue's markets still come back.
- `parse_book`: levels are [price, contracts] lists of floats. Levels with q <= 0 are dropped before the LEVELS cut, so
  a side keeps LEVELS real levels. A side missing from the payload is empty. "No book" is a None payload, or a
  Polymarket US payload with no marketData; an empty book is still a book.
- `favourite` and `offered` take the sides sorted as parse_book gives them (bids high to low, asks low to high).
- `fee` returns a float. Gemini's ceiling leaves an exact cent alone (4 contracts at 50c is 0.07, not 0.08).
  Polymarket US rounds the exact decimal value half to even: 120 at 50c is 2.085 -> 2.08, and 280 at 50c is
  4.865 -> 4.86 (Decimal of the float's binary value would give 4.87).
- `checkpoint`: before the start clips to 1, the end or later to 15.
- `rows` returns a list of row dicts (extra keys allowed). `fill` has the int stakes as keys. `spread` is compared
  approximately. A non-bet's `at_ask` isn't pinned.
- `summarise`: books, bets, settled and wins are counts (0, never None). median_at_ask and fill are over the bets.
  win_rate, mean_price, z and pnl10 are over the settled bets. A fill of exactly FULL counts as full. With no bets,
  fill is {stake: None}.
- `record`: RATE applies to book reads: one venue's reads are at least 1/RATE[v] apart on the injected clock. Listing
  and result requests aren't timed. time.sleep is made to fail, so only the injected sleep may wait. A line's `t` is the
  clock when its book was asked for (to 1 ms), and Gemini's data_t is that t. A due market is read within a few seconds
  (the 5 s cap plus rate waits), so reads are STEP to STEP + 8 s apart. Relisting and results passes happen within
  ~6 s of when they fall due. A results pass asks Gemini's recently-settled with limit=100 at offsets 0, 100 and 200
  (RESULT_PAGES pages, when the total says there are more). A Polymarket US result is GET /v1/markets with a `slug`
  param. RESULTS lines are the result dicts. A failed or empty book is logged to LOG with its sym.
- `main(argv)`: `record [days]` calls record(until=time.time() + days * 86400). days may be fractional. Without days,
  until is None or a week ahead. `report` prints one line per (v, fam, cp) with bets, each beginning with those three
  tokens ("gemini 15m 9 ..."). The checkpoints of a (v, fam) come in ascending order and its lines sit together.
  venue_books_report.json holds at least those keys (and none that summarise lacks), each entry equal to
  summarise(rows(OUT), RESULTS) after a JSON round trip. Usage, or an unknown command, returns 2 and names record and
  report.

    python -m pytest research/kalshi_15min/tests/test_venue_books.py -q
"""

from __future__ import annotations

import importlib
import itertools
import json
import math
import re
import socket
import sys
import time
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
import requests
from requests.structures import CaseInsensitiveDict

UTC = timezone.utc
T0 = 1_791_917_100                    # 2026-10-13T18:45:00Z: the window start of the spec's BTC15M2610131900
EVENTS_PATH = "/v1/prediction-markets/events"
SETTLED_PATH = "/v1/prediction-markets/events/recently-settled"
RESOLVED = "MARKET_STATUS_RESOLVED"
OPEN = "MARKET_STATUS_OPEN"


@pytest.fixture(scope="module")
def vb():
    """venue_books, imported in the fixture so a missing module fails each test cleanly."""
    return importlib.import_module("venue_books")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here may reach a venue: a fake that misses a request fails it instead of going out."""
    def refuse(*args, **kwargs):
        raise OSError("the venue_books tests never use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def in_tmp(monkeypatch, tmp_path):
    """Each test in its own empty folder: OUT, RESULTS, LOG and the report are written there, never in research/."""
    monkeypatch.chdir(tmp_path)


# ------------------------------------------------------------------ payloads, as the venues send them


def zulu(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def zulu_ms(t):
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def rfc1123(t):
    return formatdate(t, usegmt=True)           # "Tue, 13 Oct 2026 18:59:41 GMT"


def fmt(x):
    return None if x is None else repr(float(x))


NO_STRIKE = object()


def g_contract(sym, end=None, strike="82996.97", kind="reference", state="open", status="active"):
    """A Gemini contract. strike=None: the strike has no value yet; strike=NO_STRIKE: no strike at all."""
    c = {"instrumentSymbol": sym, "status": status, "marketState": state}
    if end is not None:
        c["expiryDate"] = zulu_ms(end)
    if strike is not NO_STRIKE:
        c["strike"] = {"type": kind} if strike is None else {"type": kind, "value": strike}
    return c


def g_settled(sym, side, settle="82990.5", strike="82996.97"):
    """A settled Gemini contract (side None: not resolved yet)."""
    c = {"instrumentSymbol": sym, "status": "settled" if side else "active", "marketState": "closed",
         "resolutionSide": side, "strike": {"type": "reference"} if strike is None else {"type": "reference", "value": strike}}
    if settle is not None:
        c["settlementValue"] = settle
    return c


def g_event(series, ticker, start, end, tags, contracts, status="active"):
    return {"ticker": ticker, "series": series, "status": status, "startTime": zulu_ms(start),
            "expiryDate": zulu_ms(end), "eventTags": [{"slug": s} for s in tags], "contracts": contracts}


def g_page(events, offset=0, total=None):
    return {"data": events, "pagination": {"limit": 100, "offset": offset, "total": len(events) if total is None else total}}


def g_book(bids=(), asks=()):
    level = lambda p, q: {"price": p, "amount": q, "timestamp": "1791917803"}
    return {"bids": [level(p, q) for p, q in bids], "asks": [level(p, q) for p, q in asks]}


def p_market(slug, start, end, beat="82994.44", status=OPEN, outcome=None, settle=None):
    return {"slug": slug, "status": status, "active": status == OPEN, "closed": status != OPEN,
            "assetPriceTerms": {"windowStart": zulu(start), "windowEnd": zulu(end),
                                "priceToBeat": None if beat is None else {"value": beat},
                                "settlementPrice": None if settle is None else {"value": settle}},
            "outcomePrices": outcome}


def p_book(slug, bids=(), offers=()):
    level = lambda p, q: {"px": {"value": p}, "qty": q}
    return {"marketData": {"marketSlug": slug, "bids": [level(p, q) for p, q in bids],
                           "offers": [level(p, q) for p, q in offers], "state": "MARKET_STATE_OPEN"}}


def mk(v, fam, sym, coin, start, end, strike):
    """A market dict as gemini_markets, pmus_markets and listing give it."""
    return {"v": v, "fam": fam, "sym": sym, "coin": coin, "start": start, "end": end, "strike": strike}


def route(vb, base, path, params):
    """(venue, path, query) of a get(base, path, params) call; a query in the path counts too."""
    url = f"{base}{path}"
    for v, root in (("gemini", vb.GEMINI), ("pmus", vb.PMUS)):
        if url.startswith(root):
            rest = urlsplit(url[len(root):])
            q = dict(parse_qsl(rest.query))
            q.update(dict(params or {}))
            return v, rest.path, q
    raise AssertionError(f"a request to an unknown host: {url}")


BTC15 = "GEMI-BTC15M2610131900-UP"
ETH05 = "GEMI-ETH05M2610131850-UP"
SOL1H = "GEMI-SOL1H2610131900-UP"
P15 = "cpc-btc-updown-15m-2026-10-13-1845z"
P1H = "cpc-btc-updown-1h-2026-10-13-1800z"

EVENTS = g_page([
    g_event("BTC15M", "BTC15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
            [g_contract(BTC15, T0 + 900, "82996.97")]),
    g_event("ETH05M", "ETH05M2610131850", T0, T0 + 300, ["five-minute", "up-down"],
            [g_contract(ETH05, T0 + 300, None)]),                              # no strike value yet
    g_event("SOL1H", "SOL1H2610131900", T0 - 2700, T0 + 900, ["hourly", "up-down"],
            [g_contract(SOL1H, None, "142.5")]),                               # no expiry on the contract
    g_event("XRP15M", "XRP15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
            [g_contract("GEMI-XRP15M2610131900-UP", T0 + 900, "1.3702", state="closed")]),
    g_event("ETH15M", "ETH15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
            [g_contract("GEMI-ETH15M2610131900-UP", T0 + 900, "4012.5")], status="inactive"),
    g_event("BTC1H", "BTC1H2610132000", T0 - 81900, T0 + 4500, ["daily"],             # the daily ladder on BTC1H
            [g_contract("GEMI-BTC1H2610132000-HI83000", T0 + 4500, "83000", kind="above"),
             g_contract("GEMI-BTC1H2610132000-HI84000", T0 + 4500, "84000", kind="above")]),
    g_event("BTC1H", "BTC1H2610162000", T0 - 86400, T0 + 3 * 86400 + 4500, [],       # the weekly one, untagged
            [g_contract("GEMI-BTC1H2610162000-HI85000", T0 + 3 * 86400 + 4500, "85000", kind="above")]),
    g_event("BTC", "BTC2610312000", T0 - 86400 * 12, T0 + 86400 * 18 + 4500, ["monthly"],
            [g_contract("GEMI-BTC2610312000-HI90000", T0 + 86400 * 18 + 4500, "90000", kind="above")]),
])
GEMINI_WANT = {
    BTC15: mk("gemini", "15m", BTC15, "BTC", T0, T0 + 900, 82996.97),
    ETH05: mk("gemini", "5m", ETH05, "ETH", T0, T0 + 300, None),
    SOL1H: mk("gemini", "1h", SOL1H, "SOL", T0 - 2700, T0 + 900, 142.5),
}

MARKETS = {"markets": [
    p_market(P15, T0, T0 + 900, "82994.44"),
    p_market(P1H, T0 - 2700, T0 + 900, None),                                # no price to beat (null)
    p_market("cpc-eth-updown-15m-2026-10-13-1845z", T0, T0 + 900, "4011.2"),
    p_market("cpc-btc-updown-5m-2026-10-13-1845z", T0, T0 + 300, "82994.44"),
    p_market("cpc-btc-updown-4h-2026-10-13-1600z", T0 - 9900, T0 + 4500, "82100.0"),
    p_market("cpc-btc-updown-15min-2026-10-13-1845z", T0, T0 + 900, "82994.44"),
    p_market("x-cpc-btc-updown-15m-2026-10-13-1845z", T0, T0 + 900, "82994.44"),
    p_market("cpc-btc-updown-15m-2026-10-13-1830z", T0 - 900, T0, "82950.0", status=RESOLVED,
             outcome='["1","0"]', settle="82990.1"),
]}
PMUS_WANT = {
    P15: mk("pmus", "15m", P15, "BTC", T0, T0 + 900, 82994.44),
    P1H: mk("pmus", "1h", P1H, "BTC", T0 - 2700, T0 + 900, None),
}


def by_sym(markets):
    out = {m["sym"]: m for m in markets}
    assert len(out) == len(markets), "a market came twice"
    return out


# ------------------------------------------------------------------ constants


def test_the_constants(vb):
    assert (vb.GEMINI, vb.PMUS) == ("https://api.gemini.com", "https://gateway.polymarket.us")
    assert vb.STEP == {("gemini", "5m"): 15, ("gemini", "15m"): 30, ("gemini", "1h"): 120,
                       ("pmus", "15m"): 30, ("pmus", "1h"): 60}
    assert vb.RATE == {"gemini": 1.5, "pmus": 1.0}
    assert (vb.REFRESH, vb.RESULTS_EVERY, vb.RESULT_PAGES, vb.SETTLE_AFTER, vb.LEVELS) == (120, 600, 3, 120, 10)
    assert (vb.LO, vb.HI, vb.UP, vb.FULL) == (0.90, 0.99, 0.01, 0.999)
    assert tuple(vb.STAKES) == (10, 25, 50, 100)
    assert vb.FEE == {"gemini": 0.07, "pmus": 0.0695}
    assert (vb.TRIES, vb.WEEK) == (6, 7 * 86400)
    assert (vb.OUT, vb.RESULTS, vb.LOG) == ("venue_books.jsonl", "venue_results.jsonl", "venue_books.log")


# ------------------------------------------------------------------ get


class Clock:
    """A fake clock: now() reads it, sleep() moves it on at once, and every sleep is kept."""

    def __init__(self, t):
        self.t, self.sleeps = float(t), []

    def now(self):
        return self.t

    def sleep(self, s):
        assert s >= -1e-9, f"slept a negative {s}"
        self.sleeps.append(s)
        assert len(self.sleeps) < 2_000_000, "the loop never ended"
        self.t += max(s, 0.0)


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.ok = status, body, status < 400
        self.text = json.dumps(body)
        self.content = self.text.encode()
        self.headers = CaseInsensitiveDict(headers or {"Content-Type": "application/json"})
        self.reason, self.url = "fake", ""

    def json(self, **kwargs):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class Net:
    """requests faked at Session.request: answers from a script (the last one repeats), and notes when (on the fake
    clock) each request came and what it carried."""

    def __init__(self, clock, script):
        self.clock, self.script, self.calls = clock, list(script), []

    def __call__(self, method, url, params=None, **kwargs):     # a class attribute that isn't a function: no self
        self.calls.append({"t": self.clock.t, "method": method.upper(), "url": url, "params": dict(params or {}),
                           "kwargs": kwargs})
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


_days = itertools.count(1)


@pytest.fixture
def http(monkeypatch):
    """A fake clock each test (a later day each time, so no wait is left over from the last one) and a way to script
    the venues' answers."""
    clock = Clock(T0 + 86400 * next(_days))
    monkeypatch.setattr(time, "time", clock.now)
    monkeypatch.setattr(time, "monotonic", clock.now)
    monkeypatch.setattr(time, "sleep", clock.sleep)

    def script(*answers):
        net = Net(clock, answers)
        monkeypatch.setattr(requests.Session, "request", net)
        return net
    script.clock = clock
    return script


def test_get_sends_get_base_plus_path_with_the_params_and_a_timeout(vb, http):
    body = g_book(bids=[("0.89", "800.0")], asks=[("0.91", "120.0")])
    net = http(Resp(200, body))
    data, headers = vb.get(vb.GEMINI, f"/v1/book/{BTC15}", {"depth": "10"})
    assert data == body
    [call] = net.calls
    assert (call["method"], call["url"], call["params"]) == ("GET", vb.GEMINI + f"/v1/book/{BTC15}", {"depth": "10"})
    assert call["kwargs"].get("timeout")


def test_get_without_params(vb, http):
    net = http(Resp(200, {"markets": []}))
    assert vb.get(vb.PMUS, "/v1/markets")[0] == {"markets": []}
    assert net.calls[0]["url"] == vb.PMUS + "/v1/markets" and not net.calls[0]["params"]


def test_get_returns_the_headers_case_insensitively(vb, http):
    http(Resp(200, {"marketData": {}}, headers={"Last-Modified": "Tue, 13 Oct 2026 18:59:41 GMT", "Age": "12"}))
    _, headers = vb.get(vb.PMUS, f"/v1/markets/{P15}/book")
    assert headers["last-modified"] == "Tue, 13 Oct 2026 18:59:41 GMT"
    assert headers["AGE"] == "12" and headers.get("Age") == "12"


def test_get_is_none_none_for_a_404_without_asking_again(vb, http):
    net = http(Resp(404, {"error": "not found"}))
    assert vb.get(vb.PMUS, "/v1/markets/nope/book") == (None, None)
    assert len(net.calls) == 1


def test_get_retries_429_5xx_and_connection_errors_waiting_longer_each_time(vb, http):
    net = http(Resp(429), Resp(503), requests.ConnectionError("reset"), Resp(500), Resp(200, {"ok": 1}))
    data, _ = vb.get(vb.GEMINI, EVENTS_PATH, {"category": "crypto"})
    assert data == {"ok": 1}
    times = [c["t"] for c in net.calls]
    assert len(times) == 5
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert gaps[0] > 0 and all(b > a for a, b in zip(gaps, gaps[1:])), gaps     # time.sleep, longer each time


@pytest.mark.parametrize("answer", [Resp(500), Resp(502), Resp(429), requests.ConnectionError("down")],
                         ids=["500", "502", "429", "connection"])
def test_get_raises_after_tries_tries(vb, http, answer):
    net = http(answer)
    with pytest.raises(Exception):
        vb.get(vb.GEMINI, f"/v1/book/{BTC15}")
    assert len(net.calls) == vb.TRIES


def test_get_reads_tries_when_called(vb, http, monkeypatch):
    monkeypatch.setattr(vb, "TRIES", 3)
    net = http(Resp(503))
    with pytest.raises(Exception):
        vb.get(vb.PMUS, f"/v1/markets/{P15}/book")
    assert len(net.calls) == 3


# ------------------------------------------------------------------ iso, epoch


def test_iso_is_utc_to_the_second(vb):
    assert vb.iso(T0) == "2026-10-13T18:45:00Z"
    assert vb.iso(float(T0 + 3600)) == "2026-10-13T19:45:00Z"


@pytest.mark.parametrize("s", ["2026-10-13T18:45:00.000Z", "2026-10-13T18:45:00Z", "2026-10-13T18:45:00.000",
                               "2026-10-13T18:45:00"])
def test_epoch_reads_iso_with_or_without_milliseconds_and_z(vb, s):
    assert vb.epoch(s) == T0
    assert vb.iso(vb.epoch(s)) == "2026-10-13T18:45:00Z"


# ------------------------------------------------------------------ gemini_markets


def test_gemini_markets_keeps_the_5m_15m_and_hourly_markets(vb):
    assert by_sym(vb.gemini_markets(EVENTS)) == GEMINI_WANT


def test_gemini_leaves_out_the_daily_weekly_and_monthly_ladders(vb):
    syms = {m["sym"] for m in vb.gemini_markets(EVENTS)}
    assert not {s for s in syms if "-HI" in s}
    assert not syms & {"GEMI-BTC1H2610132000-HI83000", "GEMI-BTC1H2610162000-HI85000", "GEMI-BTC2610312000-HI90000"}


def test_gemini_an_hourly_series_needs_the_hourly_tag(vb):
    event = g_event("ETH1H", "ETH1H2610131900", T0 - 2700, T0 + 900, ["hourly", "up-down"],
                    [g_contract("GEMI-ETH1H2610131900-UP", T0 + 900, "4011.0")])
    assert [m["fam"] for m in vb.gemini_markets(g_page([event]))] == ["1h"]
    event["eventTags"] = [{"slug": "daily"}, {"slug": "up-down"}]
    assert vb.gemini_markets(g_page([event])) == []


def test_gemini_skips_inactive_events_and_contracts_not_open(vb):
    syms = {m["sym"] for m in vb.gemini_markets(EVENTS)}
    assert "GEMI-XRP15M2610131900-UP" not in syms        # its contract's marketState is "closed"
    assert "GEMI-ETH15M2610131900-UP" not in syms        # its event is "inactive"


def test_gemini_one_market_per_open_contract(vb):
    event = g_event("XRP15M", "XRP15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
                    [g_contract("GEMI-XRP15M2610131900-UP", T0 + 900, "1.3702"),
                     g_contract("GEMI-XRP15M2610131900-DN", T0 + 900, "1.3702", state="closed")])
    assert [m["sym"] for m in vb.gemini_markets(g_page([event]))] == ["GEMI-XRP15M2610131900-UP"]


def test_gemini_end_is_the_contracts_expiry_else_the_events(vb):
    own = g_event("BTC15M", "BTC15M2610131900", T0, T0 + 900, ["fifteen-minute"],
                  [g_contract(BTC15, T0 + 840, "82996.97")])
    [m] = vb.gemini_markets(g_page([own]))
    assert (m["start"], m["end"]) == (T0, T0 + 840)
    own["contracts"] = [g_contract(BTC15, None, "82996.97")]
    [m] = vb.gemini_markets(g_page([own]))
    assert m["end"] == T0 + 900


@pytest.mark.parametrize("strike", [None, NO_STRIKE], ids=["no value", "no strike"])
def test_gemini_strike_missing_is_none(vb, strike):
    event = g_event("BTC05M", "BTC05M2610131850", T0, T0 + 300, ["five-minute", "up-down"],
                    [g_contract("GEMI-BTC05M2610131850-UP", T0 + 300, strike)])
    [m] = vb.gemini_markets(g_page([event]))
    assert m["strike"] is None


def test_gemini_an_empty_page(vb):
    assert vb.gemini_markets(g_page([])) == []


def test_gemini_a_malformed_event_or_contract_is_skipped_not_the_page(vb):
    """A week unattended: one odd event (no startTime) or contract (no symbol, a bad expiry) mustn't lose the rest."""
    good = g_event("BTC15M", "BTC15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
                   [g_contract(BTC15, T0 + 900, "82996.97")])
    no_start = g_event("ETH05M", "ETH05M2610131850", T0, T0 + 300, ["five-minute", "up-down"],
                       [g_contract(ETH05, T0 + 300, "4011.0")])
    del no_start["startTime"]
    bad_contracts = g_event("SOL05M", "SOL05M2610131850", T0, T0 + 300, ["five-minute", "up-down"],
                            [{"status": "active", "marketState": "open"},                  # no instrumentSymbol
                             {**g_contract("GEMI-SOL05M2610131850-UP"), "expiryDate": "soon"},
                             g_contract("GEMI-SOL05M2610131850-DN", T0 + 300, "180.1")])
    assert [m["sym"] for m in vb.gemini_markets(g_page([no_start, bad_contracts, good]))] == \
        ["GEMI-SOL05M2610131850-DN", BTC15]


# ------------------------------------------------------------------ pmus_markets


def test_pmus_markets_keeps_btc_up_down_15m_and_1h(vb):
    assert by_sym(vb.pmus_markets(MARKETS)) == PMUS_WANT


def test_pmus_markets_keeps_only_open_markets(vb):
    page = {"markets": [p_market(P15, T0, T0 + 900, "82994.44", status=RESOLVED, outcome='["1","0"]', settle="83010.12")]}
    assert vb.pmus_markets(page) == []


def test_pmus_markets_an_empty_page(vb):
    assert vb.pmus_markets({"markets": []}) == []


def test_pmus_markets_a_malformed_market_is_skipped_not_the_page(vb):
    broken = p_market("cpc-btc-updown-15m-2026-10-13-1900z", T0 + 900, T0 + 1800)
    del broken["assetPriceTerms"]["windowStart"]
    no_terms = p_market("cpc-btc-updown-1h-2026-10-13-1900z", T0, T0 + 3600)
    no_terms["assetPriceTerms"] = None
    page = {"markets": [broken, no_terms, p_market(P15, T0, T0 + 900)]}
    assert [m["sym"] for m in vb.pmus_markets(page)] == [P15]


# ------------------------------------------------------------------ listing

NEXT15 = "GEMI-BTC15M2610131915-UP"


def test_listing_pages_both_venues_and_keeps_markets_not_ended(vb, monkeypatch):
    now = T0 + 300
    g_pages = {
        0: [EVENTS["data"][0], EVENTS["data"][1],                         # BTC 15m; ETH 5m ends now: out
            g_event("BTC15M", "BTC15M2610131915", T0 + 900, T0 + 1800, ["fifteen-minute", "up-down"],
                    [g_contract(NEXT15, T0 + 1800, None)])],                # not started yet: in
        100: [EVENTS["data"][2]] + EVENTS["data"][5:],                    # SOL 1h, and ladders left out
    }
    filler = [p_market(f"cpc-eth-updown-15m-2026-10-13-{i:04d}z", T0, T0 + 900, "4011.2") for i in range(199)]
    p_pages = {0: filler + [p_market(P15, T0, T0 + 900, "82994.44")],     # a full page of 200
               200: [p_market(P1H, T0 - 2700, T0 + 900, None),
                     p_market("cpc-btc-updown-15m-2026-10-13-1830z", T0 - 900, T0, "82950.0")]}   # ended: out
    asked = []

    def get(base, path, params=None):
        v, p, q = route(vb, base, path, params)
        asked.append((v, p, q))
        assert len(asked) < 50, "the listing never ended"
        off = int(q.get("offset", 0))
        if v == "gemini":
            assert p == EVENTS_PATH
            return g_page(g_pages.get(off, []), off, 150), CaseInsensitiveDict()
        assert p == "/v1/markets"
        return {"markets": p_pages.get(off, [])}, CaseInsensitiveDict()

    monkeypatch.setattr(vb, "get", get)
    got = vb.listing(now)
    assert got == {BTC15: GEMINI_WANT[BTC15], SOL1H: GEMINI_WANT[SOL1H],
                   NEXT15: mk("gemini", "15m", NEXT15, "BTC", T0 + 900, T0 + 1800, None), **PMUS_WANT}

    g = [q for v, _, q in asked if v == "gemini"]
    assert [int(q.get("offset", 0)) for q in g] == [0, 100]               # offset += 100 while offset < total
    assert all(q["category"] == "crypto" and int(q["limit"]) == 100 for q in g)
    p = [q for v, _, q in asked if v == "pmus"]
    assert [int(q.get("offset", 0)) for q in p] == [0, 200]               # while a page holds 200
    for q in p:
        assert (q["active"], q["closed"], int(q["limit"])) == ("true", "false", 200)
        assert (q["endDateMin"], q["endDateMax"]) == ("2026-10-13T17:50:00Z", "2026-10-13T21:50:00Z")


@pytest.mark.parametrize("down", ["gemini", "pmus"])
def test_listing_a_venue_that_fails_is_logged_and_the_other_still_lists(vb, monkeypatch, capsys, down):
    def get(base, path, params=None):
        v, p, q = route(vb, base, path, params)
        if v == down:
            raise RuntimeError(f"gave up on {path}")
        if v == "gemini":
            return EVENTS, CaseInsensitiveDict()
        return MARKETS, CaseInsensitiveDict()

    monkeypatch.setattr(vb, "get", get)
    got = vb.listing(T0 + 100)
    assert got == (PMUS_WANT if down == "gemini" else GEMINI_WANT)
    out = capsys.readouterr()
    log = Path(vb.LOG).read_text(encoding="utf-8") if Path(vb.LOG).exists() else ""
    assert down in (log + out.out + out.err).lower()


# ------------------------------------------------------------------ parse_book

G_BOOK = g_book(bids=[("0.89", "800.0"), ("0.91", "120.5"), ("0.90", "0")],
                asks=[("0.94", "300.0"), ("0.93", "50.0")])
P_BOOK = p_book(P15, bids=[("0.9800", "1500.00"), ("0.9900", "20386.69"), ("0.9700", "0.00")],
                offers=[("0.9990", "4200.00"), ("0.9950", "310.50")])
LM = "Tue, 13 Oct 2026 18:59:41 GMT"
LM_T = T0 + 881                                    # 18:59:41Z


def floats(book):
    return all(isinstance(x, float) for side in ("bids", "asks") for level in book[side] for x in level)


def test_parse_book_gemini_sorts_to_floats_at_now(vb):
    b = vb.parse_book("gemini", G_BOOK, CaseInsensitiveDict({"Last-Modified": LM, "Age": "12"}), T0 + 900.5)
    assert b == {"bids": [[0.91, 120.5], [0.89, 800.0]], "asks": [[0.93, 50.0], [0.94, 300.0]], "data_t": T0 + 900.5}
    assert floats(b) and isinstance(b["data_t"], float)


def test_parse_book_pmus_offers_are_the_yes_asks(vb):
    b = vb.parse_book("pmus", P_BOOK, CaseInsensitiveDict({"Last-Modified": LM}), T0 + 900.0)
    assert b["bids"] == [[0.99, 20386.69], [0.98, 1500.0]]
    assert b["asks"] == [[0.995, 310.5], [0.999, 4200.0]]
    assert floats(b)


@pytest.mark.parametrize("headers,want", [
    ({"Last-Modified": LM, "Age": "12"}, LM_T),            # Last-Modified first
    ({"Last-Modified": LM}, LM_T),
    ({"Age": "12"}, T0 + 900.0 - 12),                      # else now - Age
    ({"Content-Type": "application/json"}, T0 + 900.0),   # else now
    (None, T0 + 900.0),
], ids=["last-modified and age", "last-modified", "age", "neither", "no headers"])
def test_parse_book_pmus_data_time(vb, headers, want):
    h = None if headers is None else CaseInsensitiveDict(headers)
    assert vb.parse_book("pmus", P_BOOK, h, T0 + 900.0)["data_t"] == pytest.approx(want)


def test_parse_book_pmus_headers_in_any_case(vb):
    assert vb.parse_book("pmus", P_BOOK, CaseInsensitiveDict({"last-modified": LM}), T0 + 900.0)["data_t"] == pytest.approx(LM_T)


def test_parse_book_keeps_the_best_levels_levels(vb, monkeypatch):
    monkeypatch.setattr(vb, "LEVELS", 3)
    b = vb.parse_book("gemini", g_book(bids=[("0.86", "5"), ("0.89", "1"), ("0.85", "5"), ("0.88", "2"), ("0.87", "3")],
                                       asks=[("0.94", "5"), ("0.90", "1"), ("0.93", "4"), ("0.91", "2"), ("0.92", "3")]),
                      None, T0)
    assert b["bids"] == [[0.89, 1.0], [0.88, 2.0], [0.87, 3.0]]
    assert b["asks"] == [[0.90, 1.0], [0.91, 2.0], [0.92, 3.0]]


def test_parse_book_drops_empty_levels_before_the_cut(vb, monkeypatch):
    monkeypatch.setattr(vb, "LEVELS", 3)
    b = vb.parse_book("pmus", p_book(P15, bids=[("0.8900", "0.00"), ("0.8800", "2.00"), ("0.8700", "-1.00"),
                                                ("0.8600", "4.00"), ("0.8500", "5.00"), ("0.8400", "6.00")],
                                     offers=[("0.9000", "0"), ("0.9100", "2.50")]), None, T0)
    assert b["bids"] == [[0.88, 2.0], [0.86, 4.0], [0.85, 5.0]]
    assert b["asks"] == [[0.91, 2.5]]


def test_parse_book_ten_levels_by_default(vb):
    bids = [(f"0.{80 + i}", "10") for i in range(14)]
    b = vb.parse_book("gemini", g_book(bids=bids), None, T0)
    assert len(b["bids"]) == 10 and b["bids"][0] == [0.93, 10.0] and b["asks"] == []


@pytest.mark.parametrize("v,payload", [("gemini", None), ("pmus", None), ("pmus", {}), ("pmus", {"marketData": None})],
                         ids=["gemini none", "pmus none", "pmus empty", "pmus no marketData"])
def test_parse_book_is_none_without_a_book(vb, v, payload):
    assert vb.parse_book(v, payload, None, T0) is None


def test_parse_book_an_empty_or_one_sided_book_is_still_a_book(vb):
    assert vb.parse_book("gemini", {"bids": [], "asks": []}, None, T0) == {"bids": [], "asks": [], "data_t": T0}
    one = {"marketData": {"marketSlug": P15, "bids": [{"px": {"value": "0.9900"}, "qty": "20386.69"}],
                          "state": "MARKET_STATE_OPEN"}}                         # no "offers" key at all
    b = vb.parse_book("pmus", one, None, T0)
    assert (b["bids"], b["asks"]) == ([[0.99, 20386.69]], [])


# ------------------------------------------------------------------ due


@pytest.mark.parametrize("now,last,want", [
    (T0 - 1, None, False), (T0, None, True), (T0 + 899, None, True), (T0 + 900, None, False),
    (T0 + 100, T0 + 70, True), (T0 + 100, T0 + 71, False), (T0 + 900, T0 + 800, False)])
def test_due_pmus_15m_every_30_s_inside_its_window(vb, now, last, want):
    assert vb.due(PMUS_WANT[P15], now, last) is want


@pytest.mark.parametrize("v,fam,step", [("gemini", "5m", 15), ("gemini", "15m", 30), ("gemini", "1h", 120),
                                        ("pmus", "1h", 60)])
def test_due_steps_by_family(vb, v, fam, step):
    m = mk(v, fam, "X", "BTC", T0 - 2700, T0 + 900, None)
    assert vb.due(m, T0 + 500, T0 + 500 - step) is True
    assert vb.due(m, T0 + 500, T0 + 500 - step + 1) is False


# ------------------------------------------------------------------ results

XRP15_DONE = "GEMI-XRP15M2610131845-UP"
BTC05_DONE = "GEMI-BTC05M2610131845-UP"
ETH1H_DONE = "GEMI-ETH1H2610131800-UP"

SETTLED = g_page([
    g_event("XRP15M", "XRP15M2610131845", T0 - 900, T0, ["fifteen-minute", "up-down"],
            [g_settled(XRP15_DONE, "yes", "1.3715519352333334", "1.3702")], status="settled"),
    g_event("BTC05M", "BTC05M2610131845", T0 - 300, T0, ["five-minute", "up-down"],
            [g_settled(BTC05_DONE, "no", "82950.1", "82996.97")], status="settled"),
    g_event("ETH1H", "ETH1H2610131800", T0 - 6300, T0 - 2700, ["hourly", "up-down"],
            [g_settled(ETH1H_DONE, "yes", None, None)], status="settled"),
    g_event("BTC1H", "BTC1H2610131800", T0 - 85500, T0 - 2700, ["daily"],
            [g_settled("GEMI-BTC1H2610131800-HI82000", "yes", "82950.1", "82000"),
             g_settled("GEMI-BTC1H2610131800-HI83000", "no", "82950.1", "83000")], status="settled"),
    g_event("BTC", "BTC2609302000", T0 - 86400 * 40, T0 - 86400 * 13, ["monthly"],
            [g_settled("GEMI-BTC2609302000-HI90000", "no", "81234.5", "90000")], status="settled"),
    g_event("SOL15M", "SOL15M2610131900", T0, T0 + 900, ["fifteen-minute", "up-down"],
            [g_settled("GEMI-SOL15M2610131900-UP", None, None, "142.5")]),          # not resolved yet
], total=1000)


def test_gemini_results_in_the_kept_families(vb):
    got = by_sym(vb.gemini_results(SETTLED))
    assert got == {
        XRP15_DONE: {"v": "gemini", "sym": XRP15_DONE, "yes": True, "settle": 1.3715519352333334, "strike": 1.3702},
        BTC05_DONE: {"v": "gemini", "sym": BTC05_DONE, "yes": False, "settle": 82950.1, "strike": 82996.97},
        ETH1H_DONE: {"v": "gemini", "sym": ETH1H_DONE, "yes": True, "settle": None, "strike": None},
    }
    assert all(isinstance(r["yes"], bool) for r in got.values())


def resolved_page(outcome, settle="83010.12", beat="82994.44", status=RESOLVED):
    return {"markets": [p_market(P15, T0, T0 + 900, beat, status=status, outcome=outcome, settle=settle)]}


def test_pmus_result_yes(vb):
    r = vb.pmus_result(resolved_page('["1","0"]'))
    assert r == {"v": "pmus", "sym": P15, "yes": True, "settle": 83010.12, "strike": 82994.44}
    assert r["yes"] is True


def test_pmus_result_no(vb):
    r = vb.pmus_result(resolved_page('["0","1"]', settle="82950.0", beat=None))
    assert r == {"v": "pmus", "sym": P15, "yes": False, "settle": 82950.0, "strike": None}
    assert r["yes"] is False


@pytest.mark.parametrize("payload", [resolved_page(None, settle=None, status=OPEN),
                                     resolved_page('["0.97","0.03"]', settle=None, status=OPEN),
                                     {"markets": []}, None],
                         ids=["open", "open with prices", "no market", "none"])
def test_pmus_result_is_none_until_resolved(vb, payload):
    assert vb.pmus_result(payload) is None


# ------------------------------------------------------------------ favourite, offered, walk


@pytest.mark.parametrize("bids,asks,want", [
    ([[0.95, 100.0]], [[0.97, 50.0]], ("yes", 0.97)),                    # mid 0.96: YES at its ask
    ([[0.02, 500.0]], [[0.04, 10.0]], ("no", 0.98)),                     # mid 0.03: NO at 1 - the YES bid
    ([[0.07, 500.0]], [[0.09, 10.0]], ("no", 0.93)),                     # 1 - 0.07 = 0.9299999999999999, rounded
    ([[0.4, 1.0]], [[0.6, 1.0]], ("yes", 0.6)),                          # mid exactly 0.5 is YES
    ([[0.39, 1.0]], [[0.6, 1.0]], ("no", 0.61)),                         # mid 0.495 is NO
    ([[0.99, 10.0]], [], ("yes", None)),                                 # YES bid 0.99, nothing offered on YES
    ([], [[0.03, 10.0]], ("no", None)),                                  # YES ask 0.03: NO, but no YES bid to sell
    ([], [[0.97, 10.0]], ("yes", 0.97)),
    ([[0.06, 10.0]], [], ("no", 0.94)),
    ([[0.95, 100.0], [0.94, 9.0]], [[0.97, 50.0], [0.98, 9.0]], ("yes", 0.97)),   # the best levels
    ([], [], (None, None)),
], ids=["yes", "no", "no rounded", "half", "under half", "one-sided bid", "one-sided ask", "yes no bid",
        "no no ask", "deeper", "empty"])
def test_favourite(vb, bids, asks, want):
    assert tuple(vb.favourite(bids, asks)) == want


def test_offered_yes_takes_the_asks_up_to_the_limit_rounding_first(vb):
    asks = [[0.93, 10.0], [0.94, 20.0], [0.95, 30.0]]
    assert vb.offered("yes", [[0.9, 5.0]], asks, 0.93 + 0.01) == [[0.93, 10.0], [0.94, 20.0]]    # 0.9400000000000001
    asks = [[0.95, 10.0], [0.96, 20.0], [0.97, 30.0]]
    assert vb.offered("yes", [[0.9, 5.0]], asks, 0.95 + 0.01) == [[0.95, 10.0], [0.96, 20.0]]


def test_offered_no_turns_the_yes_bids_into_no_prices_cheapest_first(vb):
    bids = [[0.07, 100.0], [0.06, 200.0], [0.05, 300.0]]
    assert vb.offered("no", bids, [[0.09, 5.0]], 0.93 + 0.01) == [[0.93, 100.0], [0.94, 200.0]]
    assert vb.offered("no", bids, [], 0.99) == [[0.93, 100.0], [0.94, 200.0], [0.95, 300.0]]


def test_offered_nothing(vb):
    assert vb.offered("yes", [[0.9, 5.0]], [], 0.99) == []
    assert vb.offered("no", [], [[0.5, 5.0]], 0.99) == []
    assert vb.offered("yes", [], [[0.97, 5.0]], 0.96) == []
    assert vb.offered("no", [[0.02, 5.0]], [], 0.97) == []


def test_walk_takes_the_last_level_in_part(vb):
    c, cost = vb.walk([[0.95, 5.0], [0.96, 100.0]], 10)
    assert c == pytest.approx(5 + 5.25 / 0.96) and cost == pytest.approx(10.0)


def test_walk_takes_what_there_is_when_the_book_runs_out(vb):
    c, cost = vb.walk([[0.95, 5.0], [0.96, 2.0]], 10)
    assert c == pytest.approx(7.0) and cost == pytest.approx(4.75 + 1.92)


def test_walk_exactly_enough_and_nothing(vb):
    c, cost = vb.walk([[0.5, 20.0]], 10)
    assert c == pytest.approx(20.0) and cost == pytest.approx(10.0)
    assert tuple(vb.walk([], 10)) == (0, 0)


# ------------------------------------------------------------------ fee


@pytest.mark.parametrize("c,p,want", [
    (10, 0.95, 0.04),            # 0.03325 rounds up
    (2, 0.9, 0.02),              # 0.0126
    (1000, 0.99, 0.70),          # 0.693
    (4, 0.5, 0.07),              # exactly 0.07 (0.07000000000000001 in floats): not 0.08
    (20, 0.5, 0.35),             # 0.35000000000000003 in floats
    (100, 0.5, 1.75),            # 1.7500000000000002 in floats
    (10 + 0.4 / 0.97, 10 / (10 + 0.4 / 0.97), 0.03),
])
def test_gemini_fee_rounds_up_to_the_cent(vb, c, p, want):
    f = vb.fee("gemini", c, p)
    assert isinstance(f, float) and f == pytest.approx(want, abs=1e-9)


@pytest.mark.parametrize("c,p,want", [
    (10, 0.95, 0.03),            # 0.0330125: to the nearest cent, not up
    (100, 0.9, 0.63),            # 0.6255
    (120, 0.5, 2.08),            # 2.085: half to even goes down
    (280, 0.5, 4.86),            # 4.865: down too (the float 4.865 is a hair over)
    (40, 0.5, 0.70),             # 0.695: half to even goes up
    (10 / 0.97, 0.97, 0.02),     # 0.02085
])
def test_pmus_fee_rounds_half_to_even(vb, c, p, want):
    f = vb.fee("pmus", c, p)
    assert isinstance(f, float) and f == pytest.approx(want, abs=1e-9)


@pytest.mark.parametrize("v", ["gemini", "pmus"])
def test_no_contracts_no_fee(vb, v):
    assert vb.fee(v, 0, 0.95) == 0


# ------------------------------------------------------------------ checkpoint


@pytest.mark.parametrize("start,end,k,want", [
    (T0, T0 + 900, 0, 1), (T0, T0 + 900, 59.9, 1), (T0, T0 + 900, 60, 2), (T0, T0 + 900, 480, 9),
    (T0, T0 + 900, 539.9, 9), (T0, T0 + 900, 899, 15), (T0, T0 + 900, 900, 15), (T0, T0 + 900, 1000, 15),
    (T0, T0 + 900, -5, 1), (T0, T0 + 900, -65, 1),
    (T0, T0 + 300, 100, 6), (T0, T0 + 300, 160, 9),                     # 5 minutes: 20 s a checkpoint
    (T0 - 2700, T0 + 900, 1920, 9), (T0 - 2700, T0 + 900, 1919, 8),     # an hour: 240 s a checkpoint
])
def test_checkpoint_is_the_minute_of_15(vb, start, end, k, want):
    assert vb.checkpoint({"start": start, "end": end, "data_t": start + k, "k": k}) == want


# ------------------------------------------------------------------ rows


def brec(v, fam, sym, start, end, data_t, bids, asks, coin="BTC", strike=82996.97):
    """A recorded book, as record() writes it."""
    return {"v": v, "fam": fam, "sym": sym, "coin": coin, "start": start, "end": end, "strike": strike,
            "t": data_t + 0.2, "data_t": data_t, "k": data_t - start, "bids": bids, "asks": asks}


def keyed(rows):
    rows = list(rows)
    out = {(r["v"], r["fam"], r["sym"], r["cp"]): r for r in rows}
    assert len(out) == len(rows), "two rows for one (v, fam, sym, cp)"
    return out


def test_rows_one_per_checkpoint_from_its_first_book(vb):
    early = [[0.95, 100.0]], [[0.96, 500.0]]
    late = [[0.40, 100.0]], [[0.45, 500.0]]
    recs = [
        brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 485, *late),          # checkpoint 9, read second
        brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 481, *early),         # checkpoint 9, read first
        brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 545, *late),          # checkpoint 10
        brec("gemini", "5m", ETH05, T0, T0 + 300, T0 + 161, *early, coin="ETH"),   # 5 minutes: checkpoint 9
    ]
    got = keyed(vb.rows(recs))
    assert set(got) == {("gemini", "15m", BTC15, 9), ("gemini", "15m", BTC15, 10), ("gemini", "5m", ETH05, 9)}
    assert (got[("gemini", "15m", BTC15, 9)]["side"], got[("gemini", "15m", BTC15, 9)]["price"]) == ("yes", 0.96)
    assert got[("gemini", "15m", BTC15, 10)]["side"] == "no"
    assert got[("gemini", "5m", ETH05, 9)]["coin"] == "ETH"


def test_rows_a_yes_bet(vb):
    [r] = vb.rows([brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 481,
                        [[0.95, 100.0]], [[0.96, 10.0], [0.97, 20.0], [0.98, 1000.0]])])
    assert {k: r[k] for k in ("v", "fam", "sym", "coin", "cp", "side", "price", "bet")} == {
        "v": "gemini", "fam": "15m", "sym": BTC15, "coin": "BTC", "cp": 9, "side": "yes", "price": 0.96, "bet": True}
    assert r["spread"] == pytest.approx(0.01)
    assert r["at_ask"] == pytest.approx(9.6)                         # only the 96c level
    assert set(r["fill"]) == {10, 25, 50, 100}                       # up to 97c: $9.60 + $19.40 = $29
    assert r["fill"] == pytest.approx({10: 1.0, 25: 1.0, 50: 0.58, 100: 0.29})
    assert all(s <= 1.0 for s in r["fill"].values())
    c = 10 + 0.4 / 0.97                                              # 10 at 96c, the last 40c at 97c
    pu = r["pnl_unit"]
    assert pu["contracts"] == pytest.approx(c) and pu["cost"] == pytest.approx(10.0)
    assert pu["fee"] == pytest.approx(0.03)                          # 0.07 x 10 x (1 - 0.9604) = 0.0277, up


def test_rows_a_no_bet_walks_the_yes_bids(vb):
    [r] = vb.rows([brec("pmus", "15m", P15, T0, T0 + 900, T0 + 485,
                        [[0.03, 400.0], [0.02, 1000.0]], [[0.05, 50.0]], strike=82994.44)])
    assert (r["v"], r["cp"], r["side"], r["price"], r["bet"]) == ("pmus", 9, "no", 0.97, True)
    assert r["spread"] == pytest.approx(0.02)
    assert r["at_ask"] == pytest.approx(388.0)                       # 400 NO at 97c, from the YES bid at 3c
    assert r["fill"] == pytest.approx({10: 1.0, 25: 1.0, 50: 1.0, 100: 1.0})
    pu = r["pnl_unit"]
    assert pu["contracts"] == pytest.approx(10 / 0.97) and pu["cost"] == pytest.approx(10.0)
    assert pu["fee"] == pytest.approx(0.02)                          # Polymarket US: 0.02085 to the nearest cent


@pytest.mark.parametrize("bids,asks,price,bet", [
    ([[0.88, 10.0]], [[0.90, 10.0]], 0.90, True),            # YES at 90c: in
    ([[0.98, 10.0]], [[0.99, 10.0]], 0.99, True),            # YES at 99c: in
    ([[0.10, 10.0]], [[0.12, 10.0]], 0.90, True),            # NO at 1 - 0.10: in
    ([[0.01, 10.0]], [[0.02, 10.0]], 0.99, True),            # NO at 1 - 0.01: in
    ([[0.88, 10.0]], [[0.8999, 10.0]], 0.8999, False),       # just under
    ([[0.98, 10.0]], [[0.9901, 10.0]], 0.9901, False),       # just over
    ([[0.1001, 10.0]], [[0.12, 10.0]], 0.8999, False),
    ([[0.0099, 10.0]], [[0.02, 10.0]], 0.9901, False),
    ([[0.55, 10.0]], [[0.60, 10.0]], 0.60, False),
], ids=["yes 90", "yes 99", "no 90", "no 99", "yes 89.99", "yes 99.01", "no 89.99", "no 99.01", "yes 60"])
def test_rows_the_bet_band_is_90_to_99c_inclusive(vb, bids, asks, price, bet):
    [r] = vb.rows([brec("pmus", "15m", P15, T0, T0 + 900, T0 + 485, bids, asks)])
    assert r["price"] == pytest.approx(price) and r["bet"] is bet
    if not bet:
        assert r["fill"] == {} and r["pnl_unit"] is None


def test_rows_one_sided_and_empty_books_are_not_bets(vb):
    got = keyed(vb.rows([brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 481, [[0.99, 10.0]], []),
                         brec("gemini", "15m", NEXT15, T0, T0 + 900, T0 + 482, [], [])]))
    one, empty = got[("gemini", "15m", BTC15, 9)], got[("gemini", "15m", NEXT15, 9)]
    assert (one["side"], one["price"], one["bet"], one["spread"]) == ("yes", None, False, None)
    assert one["fill"] == {} and one["pnl_unit"] is None
    assert (empty["side"], empty["price"], empty["bet"], empty["spread"]) == (None, None, False, None)
    assert empty["fill"] == {} and empty["pnl_unit"] is None


# ------------------------------------------------------------------ summarise


def row(v, fam, sym, cp, side, price, spread, at_ask=0.0, fill=None, pnl=None):
    bet = price is not None and 0.90 <= price <= 0.99
    return {"v": v, "fam": fam, "sym": sym, "coin": "BTC", "cp": cp, "side": side, "price": price, "bet": bet,
            "spread": spread, "at_ask": at_ask, "fill": fill or {}, "pnl_unit": pnl}


def res(v, sym, yes):
    return {"v": v, "sym": sym, "yes": yes, "settle": 83000.0, "strike": 82996.97}


def fills(a, b, c, d):
    return {10: a, 25: b, 50: c, 100: d}


def check(stats, want):
    for k, w in want.items():
        got = stats[k]
        if isinstance(w, dict):
            assert set(got) == set(w), k
            for s, x in w.items():
                assert (got[s] is None) if x is None else got[s] == pytest.approx(x), (k, s)
        elif w is None:
            assert got is None, k
        else:
            assert got == pytest.approx(w), k


def test_summarise(vb):
    g = lambda sym, *a, **k: row("gemini", "15m", sym, 9, *a, **k)
    rows = [
        g("A", "yes", 0.96, 0.01, 4.8, fills(0.48, 0.192, 0.096, 0.048),
          {"contracts": 5.0, "cost": 4.8, "fee": 0.02}),                          # won, at $4.80 only
        g("B", "no", 0.95, 0.03, 200.0, fills(1.0, 1.0, 1.0, 1.0),
          {"contracts": 10 / 0.95, "cost": 10.0, "fee": 0.04}),                   # NO lost
        g("C", "yes", 0.92, 0.02, 50.0, fills(0.999, 1.0, 0.9989, 0.5),
          {"contracts": 10 / 0.92, "cost": 10.0, "fee": 0.05}),                   # not settled
        g("D", "yes", 0.60, 0.01, 30.0),                                          # not a bet, though settled
        g("E", None, None, None),                                                 # an empty book
        g("F", "no", 0.97, None, 100.0, fills(1.0, 1.0, 1.0, 0.97),
          {"contracts": 10 / 0.97, "cost": 10.0, "fee": 0.02}),                   # NO won; no spread
        g("G", "yes", 0.93, 0.04, 0.0, fills(0.0, 0.0, 0.0, 0.0), None),          # won, but nothing filled
        row("gemini", "15m", "H", 10, "yes", 0.95, 0.01, 95.0, fills(1.0, 1.0, 1.0, 0.95),
            {"contracts": 10 / 0.95, "cost": 10.0, "fee": 0.04}),                 # a checkpoint later, not settled
        row("pmus", "1h", P1H, 9, "yes", 0.60, 0.02, 6.0),
        row("pmus", "1h", "Q", 9, None, None, None),
    ]
    results = {"A": res("gemini", "A", True), "B": res("gemini", "B", True), "D": res("gemini", "D", True),
               "F": res("gemini", "F", False), "G": res("gemini", "G", True), P1H: res("pmus", P1H, True)}
    s = vb.summarise(rows, results)
    assert set(s) == {("gemini", "15m", 9), ("gemini", "15m", 10), ("pmus", "1h", 9)}

    prices = [0.96, 0.95, 0.97, 0.93]                     # the settled bets: A, B, F, G
    pnl = [(5 - 4.8 - 0.02) / 4.8 * 10, (0 - 10 - 0.04) / 10 * 10, (10 / 0.97 - 10 - 0.02) / 10 * 10]
    nine = s[("gemini", "15m", 9)]
    assert (nine["books"], nine["bets"], nine["settled"], nine["wins"]) == (7, 5, 4, 3)
    check(nine, {"median_spread": 0.02, "median_at_ask": 50.0, "fill": fills(0.6, 0.6, 0.4, 0.2),
                 "win_rate": 0.75, "mean_price": sum(prices) / 4,
                 "z": (3 - sum(prices)) / math.sqrt(sum(p * (1 - p) for p in prices)),
                 "pnl10": sum(pnl) / 3})

    ten = s[("gemini", "15m", 10)]
    assert (ten["books"], ten["bets"], ten["settled"], ten["wins"]) == (1, 1, 0, 0)
    check(ten, {"median_spread": 0.01, "median_at_ask": 95.0, "fill": fills(1.0, 1.0, 1.0, 0.0),
                "win_rate": None, "mean_price": None, "z": None, "pnl10": None})

    hour = s[("pmus", "1h", 9)]
    assert (hour["books"], hour["bets"], hour["settled"], hour["wins"]) == (2, 0, 0, 0)
    check(hour, {"median_spread": 0.02, "median_at_ask": None, "fill": fills(None, None, None, None),
                 "win_rate": None, "mean_price": None, "z": None, "pnl10": None})


def test_summarise_nothing(vb):
    assert vb.summarise([], {}) == {}


# ------------------------------------------------------------------ record

S0 = T0 - 100                       # record() starts 100 s before the 18:45 windows open
LAG = 7                             # Polymarket US books come from Cloudflare's cache, last modified 7 s earlier
G_DEFAULT = g_book(bids=[("0.95", "100.0")], asks=[("0.96", "500.0")])
G_PARSED = ([[0.95, 100.0]], [[0.96, 500.0]])
P_PARSED = ([[0.03, 400.0]], [[0.05, 50.0]])

G5 = mk("gemini", "5m", "GEMI-BTC05M2610131850-UP", "BTC", T0, T0 + 300, 82996.97)
G15 = mk("gemini", "15m", "GEMI-ETH15M2610131900-UP", "ETH", T0, T0 + 900, 4012.5)
G1H = mk("gemini", "1h", SOL1H, "SOL", T0 - 2700, T0 + 900, 142.5)          # running when record() starts
M15 = mk("pmus", "15m", P15, "BTC", T0, T0 + 900, 82994.44)
M1H = mk("pmus", "1h", P1H, "BTC", T0 - 2700, T0 + 900, 82710.05)           # running when record() starts
SCENE = [G5, G15, G1H, M15, M1H]
BUSY = [mk("gemini", fam, f"GEMI-{coin}{series}{close}-UP", coin, T0, T0 + length, 1.5 + i)    # 8 at once, + 1h
        for i, coin in enumerate(["BTC", "ETH", "SOL", "XRP"])
        for fam, series, length, close in (("5m", "05M", 300, "2610131850"), ("15m", "15M", 900, "2610131900"))
        ] + [G1H, M15, M1H]
SUFFIX = {"5m": "05M", "15m": "15M", "1h": "1H"}
TAG = {"5m": "five-minute", "15m": "fifteen-minute", "1h": "hourly"}
FILLER = [g_event("BTC1H", f"BTC1H26{i:08d}", T0 - 86400, T0 - 3600, ["daily"],
                  [g_settled(f"GEMI-BTC1H26{i:08d}-HI{80000 + i}", "yes", "82950.1", str(80000 + i))],
                  status="settled") for i in range(1000)]           # settled ladders, out of the families


def p_default(slug):
    return p_book(slug, bids=[("0.0300", "400.00")], offers=[("0.0500", "50.00")])


def event_of(m, contract, status="active"):
    return g_event(m["coin"] + SUFFIX[m["fam"]], m["sym"][len("GEMI-"):-len("-UP")], m["start"], m["end"],
                   [TAG[m["fam"]], "up-down"], [contract], status=status)


class World:
    """Both venues for record(): what each lists at the fake clock's time (each market from `shows`, if given, until
    its end), each market's book (Polymarket US's with a Last-Modified LAG s old), syms whose book fails or is a 404,
    Gemini settlements ({sym: (yes, settle, from)}, on the second page of recently-settled), Polymarket US
    resolutions ({slug: (yes, settle, from)}) and (venue, path) pairs that fail. Notes every request."""

    def __init__(self, vb, clock, markets, books=None, fail=(), none=(), shows=None, settled=None, resolved=None,
                 broken=()):
        self.vb, self.clock, self.markets, self.by = vb, clock, list(markets), {m["sym"]: m for m in markets}
        self.books, self.fail, self.none, self.shows = books or {}, set(fail), set(none), shows or {}
        self.settled, self.resolved, self.broken = settled or {}, resolved or {}, set(broken)
        self.calls, self.unexpected = [], []

    def listed(self, v, t):
        return [m for m in self.markets if m["v"] == v and self.shows.get(m["sym"], -math.inf) <= t < m["end"]]

    def __call__(self, base, path, params=None):
        v, p, q = route(self.vb, base, path, params)
        t = self.clock.t
        self.calls.append((t, v, p, q))
        if (v, p) in self.broken:
            raise RuntimeError(f"{v} {p}: down")
        plain = CaseInsensitiveDict({"Content-Type": "application/json"})
        off = int(q.get("offset", 0))
        if v == "gemini" and p == EVENTS_PATH:
            evs = [event_of(m, g_contract(m["sym"], m["end"], fmt(m["strike"]))) for m in self.listed("gemini", t)]
            return g_page(evs[off:off + int(q.get("limit", 100))], off, len(evs)), plain
        if v == "gemini" and p == SETTLED_PATH:
            done = [event_of(self.by[s], g_settled(s, "yes" if yes else "no", settle, fmt(self.by[s]["strike"])),
                             status="settled") for s, (yes, settle, since) in self.settled.items() if t >= since]
            evs = (FILLER[:100] + done + FILLER[100:])[:1000] if self.settled else []
            return g_page(evs[off:off + int(q.get("limit", 100))], off, len(evs)), plain
        if v == "gemini" and p.startswith("/v1/book/"):
            return self.book(p[len("/v1/book/"):], plain)
        if v == "pmus" and p == "/v1/markets" and "slug" in q:
            m, r = self.by[q["slug"]], self.resolved.get(q["slug"])
            if r and t >= r[2]:
                return {"markets": [p_market(m["sym"], m["start"], m["end"], fmt(m["strike"]), status=RESOLVED,
                                             outcome='["1","0"]' if r[0] else '["0","1"]', settle=r[1])]}, plain
            return {"markets": [p_market(m["sym"], m["start"], m["end"], fmt(m["strike"]))]}, plain
        if v == "pmus" and p == "/v1/markets":
            ms = [p_market(m["sym"], m["start"], m["end"], fmt(m["strike"])) for m in self.listed("pmus", t)]
            return {"markets": ms[off:off + int(q.get("limit", 200))]}, plain
        if v == "pmus" and p.startswith("/v1/markets/") and p.endswith("/book"):
            cached = CaseInsensitiveDict({"Content-Type": "application/json",
                                          "Last-Modified": rfc1123(math.floor(t) - LAG), "Age": str(LAG)})
            return self.book(p[len("/v1/markets/"):-len("/book")], cached)
        self.unexpected.append((t, v, p, q))
        raise AssertionError(f"unexpected request {v} {p} {q}")

    def book(self, sym, headers):
        if sym not in self.by:
            self.unexpected.append((self.clock.t, "book", sym))
            raise AssertionError(f"a book for an unknown market {sym}")
        if sym in self.fail:
            raise requests.ConnectionError(f"{sym}: down")
        if sym in self.none:
            return None, None
        default = G_DEFAULT if self.by[sym]["v"] == "gemini" else p_default(sym)
        return self.books.get(sym, default), headers

    def requests(self, v, p, **match):
        return [(t, q) for t, v2, p2, q in self.calls if v2 == v and p2 == p
                and all(str(q.get(k, "0" if k == "offset" else None)) == str(x) for k, x in match.items())]

    def reads(self, sym=None):
        """[(t, venue, sym)] of every book asked for, or only `sym`'s."""
        out = []
        for t, v, p, _ in self.calls:
            s = p[len("/v1/book/"):] if p.startswith("/v1/book/") else \
                p[len("/v1/markets/"):-len("/book")] if p.startswith("/v1/markets/") and p.endswith("/book") else None
            if s is not None and (sym is None or s == sym):
                out.append((t, v, s))
        return out


@pytest.fixture
def world(vb, monkeypatch):
    """record()'s venues and clock; time.sleep fails, so only the injected sleep may wait."""
    def real_sleep(s):
        raise AssertionError("record() must wait with the sleep it was given")
    monkeypatch.setattr(time, "sleep", real_sleep)
    clock = Clock(S0)

    def make(markets, **kw):
        w = World(vb, clock, markets, **kw)
        monkeypatch.setattr(vb, "get", w)
        return w
    make.clock = clock
    return make


def lines(path):
    if not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def logged(vb):
    return Path(vb.LOG).read_text(encoding="utf-8") if Path(vb.LOG).exists() else ""


def test_record_writes_a_line_per_book_read(vb, world):
    w = world(SCENE)
    vb.record(until=S0 + 1100, now=world.clock.now, sleep=world.clock.sleep)
    assert not w.unexpected
    got, reads = lines(vb.OUT), w.reads()
    assert len(got) == len(reads) and {x["sym"] for x in got} == {m["sym"] for m in SCENE}
    for x in got:
        m = w.by[x["sym"]]
        assert set(x) == {"v", "fam", "sym", "coin", "start", "end", "strike", "t", "data_t", "k", "bids", "asks"}
        assert {k: x[k] for k in m} == m
        [asked] = [t for t, _, s in reads if s == x["sym"] and abs(t - x["t"]) < 1e-3]   # t: when it was asked for
        if m["v"] == "gemini":
            assert x["data_t"] == pytest.approx(asked, abs=1e-3)
            assert (x["bids"], x["asks"]) == G_PARSED
        else:
            assert x["data_t"] == pytest.approx(math.floor(asked) - LAG)                # from Last-Modified
            assert (x["bids"], x["asks"]) == P_PARSED
        assert x["k"] == pytest.approx(x["data_t"] - m["start"])


def test_record_reads_each_market_every_step_inside_its_window(vb, world):
    until = S0 + 1100
    w = world(SCENE)
    vb.record(until=until, now=world.clock.now, sleep=world.clock.sleep)
    for m in SCENE:
        ts = [t for t, _, _ in w.reads(m["sym"])]
        step = vb.STEP[(m["v"], m["fam"])]
        assert ts and all(m["start"] <= t < m["end"] for t in ts), m["sym"]
        assert ts[0] <= max(m["start"], S0) + 8, m["sym"]                # read as soon as it opens
        assert ts[-1] >= m["end"] - step - 8, m["sym"]                   # and until it closes
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        assert all(step - 1e-6 <= g <= step + 8 for g in gaps), (m["sym"], gaps)


def test_record_keeps_each_venue_under_its_rate(vb, world):
    w = world(BUSY)
    vb.record(until=S0 + 1100, now=world.clock.now, sleep=world.clock.sleep)
    assert not w.unexpected
    for v in ("gemini", "pmus"):
        ts = sorted(t for t, v2, _ in w.reads() if v2 == v)
        assert len(ts) > 20
        assert all(b - a >= 1 / vb.RATE[v] - 1e-6 for a, b in zip(ts, ts[1:])), v
    assert len(lines(vb.OUT)) == len(w.reads())


def test_record_sleeps_at_most_5_seconds_and_stops_at_until(vb, world):
    world(SCENE)
    vb.record(until=S0 + 1100, now=world.clock.now, sleep=world.clock.sleep)
    assert world.clock.sleeps and max(world.clock.sleeps) <= 5 + 1e-9
    assert S0 + 1100 <= world.clock.t < S0 + 1100 + 6


def test_record_runs_a_week_by_default(vb, world):
    world([])
    vb.record(now=world.clock.now, sleep=world.clock.sleep)
    assert S0 + 7 * 86400 <= world.clock.t < S0 + 7 * 86400 + 6
    assert max(world.clock.sleeps) <= 5 + 1e-9


def test_a_failed_or_missing_book_is_logged_and_leaves_no_line(vb, world):
    w = world(SCENE, fail={G15["sym"]}, none={M15["sym"]})
    vb.record(until=S0 + 400, now=world.clock.now, sleep=world.clock.sleep)
    got = {x["sym"] for x in lines(vb.OUT)}
    assert w.reads(G15["sym"]) and w.reads(M15["sym"])                 # asked for
    assert got == {G5["sym"], G1H["sym"], M1H["sym"]}                   # and no line; the rest still read
    log = logged(vb)
    assert G15["sym"] in log and M15["sym"] in log


def test_record_lists_at_the_start_and_every_refresh_and_reads_new_markets(vb, world):
    new = mk("gemini", "5m", "GEMI-XRP05M2610131855-UP", "XRP", T0 + 300, T0 + 600, 1.3702)   # listed from S0 + 300
    w = world([G15, M15, new], shows={new["sym"]: S0 + 300})
    vb.record(until=S0 + 590, now=world.clock.now, sleep=world.clock.sleep)
    for v, p in (("gemini", EVENTS_PATH), ("pmus", "/v1/markets")):
        ts = [t for t, q in w.requests(v, p, offset=0) if "slug" not in q]
        assert len(ts) == 5, (v, ts)                                     # at about +0, +120, +240, +360, +480
        assert ts[0] <= S0 + 1
        assert all(vb.REFRESH - 1e-6 <= b - a <= vb.REFRESH + 6 for a, b in zip(ts, ts[1:])), (v, ts)
    ts = [t for t, _, _ in w.reads(new["sym"])]
    assert ts and new["start"] <= ts[0] <= new["start"] + 8              # relisted at about +360, read from +400


def test_record_results_pass_at_the_start_and_every_results_every(vb, world):
    w = world([G5, M15], settled={G5["sym"]: (True, "82990.5", S0 + 450)})
    vb.record(until=S0 + 1300, now=world.clock.now, sleep=world.clock.sleep)
    calls = w.requests("gemini", SETTLED_PATH)
    starts = [t for t, q in calls if int(q.get("offset", 0)) == 0]
    assert len(starts) == 3 and starts[0] <= S0 + 10                    # at about +0, +600, +1200
    assert all(vb.RESULTS_EVERY - 1e-6 <= b - a <= vb.RESULTS_EVERY + 6 for a, b in zip(starts, starts[1:]))
    assert [int(q.get("offset", 0)) for _, q in calls] == [0, 100, 200] * 3     # RESULT_PAGES pages a pass
    assert all(int(q["limit"]) == 100 for _, q in calls)


def test_record_appends_each_result_once_and_asks_pmus_only_after_settle_after(vb, world):
    w = world([G5, M15], settled={G5["sym"]: (True, "82990.5", S0 + 450)},
              resolved={M15["sym"]: (False, "82950.0", S0 + 1500)})
    vb.record(until=S0 + 2500, now=world.clock.now, sleep=world.clock.sleep)
    assert not w.unexpected
    got = lines(vb.RESULTS)
    keys = ("v", "sym", "yes", "settle", "strike")
    assert sorted(({k: r[k] for k in keys} for r in got), key=lambda r: r["v"]) == [
        {"v": "gemini", "sym": G5["sym"], "yes": True, "settle": 82990.5, "strike": 82996.97},
        {"v": "pmus", "sym": M15["sym"], "yes": False, "settle": 82950.0, "strike": 82994.44}]
    asks = [t for t, q in w.requests("pmus", "/v1/markets") if q.get("slug") == M15["sym"]]
    assert len(asks) == 2                                               # about +1200 (not yet), +1800 (resolved)
    assert all(t >= M15["end"] + vb.SETTLE_AFTER - 1e-6 for t in asks)


def test_record_waits_settle_after_past_the_end(vb, world, monkeypatch):
    monkeypatch.setattr(vb, "SETTLE_AFTER", 250)                       # +1250: the pass at about +1200 is too soon
    w = world([M15], resolved={M15["sym"]: (True, "83010.12", S0 + 1500)})
    vb.record(until=S0 + 2500, now=world.clock.now, sleep=world.clock.sleep)
    asks = [t for t, q in w.requests("pmus", "/v1/markets") if q.get("slug") == M15["sym"]]
    assert len(asks) == 1 and asks[0] >= M15["end"] + 250
    assert [r["sym"] for r in lines(vb.RESULTS)] == [M15["sym"]]


def test_record_resumes_from_the_results_already_there(vb, world):
    old = [{"v": "gemini", "sym": G5["sym"], "yes": True, "settle": 82990.5, "strike": 82996.97},
           {"v": "pmus", "sym": M15["sym"], "yes": False, "settle": 82950.0, "strike": 82994.44}]
    Path(vb.RESULTS).write_text("".join(json.dumps(r) + "\n" for r in old), encoding="utf-8")
    w = world([G5, G15, M15], settled={G5["sym"]: (True, "82990.5", S0 + 450), G15["sym"]: (False, "4001.25", S0 + 1100)},
              resolved={M15["sym"]: (False, "82950.0", S0 + 1500)})
    vb.record(until=S0 + 2500, now=world.clock.now, sleep=world.clock.sleep)
    got = lines(vb.RESULTS)
    assert got[:2] == old                                              # kept, and appended to
    assert [r["sym"] for r in got] == [G5["sym"], M15["sym"], G15["sym"]]
    assert {k: got[2][k] for k in ("v", "yes", "settle", "strike")} == {"v": "gemini", "yes": False,
                                                                        "settle": 4001.25, "strike": 4012.5}
    assert not [q for _, q in w.requests("pmus", "/v1/markets") if q.get("slug") == M15["sym"]]


def test_record_carries_on_past_a_failing_pass(vb, world):
    w = world(SCENE, broken={("gemini", SETTLED_PATH)})
    vb.record(until=S0 + 700, now=world.clock.now, sleep=world.clock.sleep)
    assert w.requests("gemini", SETTLED_PATH)                          # tried, and it failed
    assert world.clock.t >= S0 + 700
    assert [t for t, _, _ in w.reads(G15["sym"]) if t > S0 + 610]      # still reading books after the second pass
    assert logged(vb)


# ------------------------------------------------------------------ main


def called_until(args, kwargs):
    return kwargs["until"] if "until" in kwargs else args[0] if args else None


@pytest.fixture
def recorder(vb, monkeypatch):
    calls = []
    monkeypatch.setattr(vb, "record", lambda *a, **k: calls.append((a, k)))
    return calls


def test_main_record_for_some_days(vb, recorder):
    vb.main(["record", "2"])
    [(args, kwargs)] = recorder
    assert called_until(args, kwargs) == pytest.approx(time.time() + 2 * 86400, abs=120)


def test_main_record_part_of_a_day(vb, recorder):
    vb.main(["record", "0.5"])
    [(args, kwargs)] = recorder
    assert called_until(args, kwargs) == pytest.approx(time.time() + 43200, abs=120)


def test_main_record_defaults_to_a_week(vb, recorder):
    vb.main(["record"])
    [(args, kwargs)] = recorder
    until = called_until(args, kwargs)
    assert until is None or until == pytest.approx(time.time() + 7 * 86400, abs=120)


def test_main_reads_sys_argv(vb, recorder, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["venue_books.py", "record", "2"])
    vb.main()
    [(args, kwargs)] = recorder
    assert called_until(args, kwargs) == pytest.approx(time.time() + 2 * 86400, abs=120)


@pytest.mark.parametrize("argv", [[], ["bogus"], None], ids=["nothing", "unknown", "sys.argv"])
def test_main_usage_returns_2(vb, recorder, monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", ["venue_books.py"])
    assert vb.main(argv) == 2
    out = capsys.readouterr()
    text = (out.out + out.err).lower()
    assert "record" in text and "report" in text
    assert recorder == []


def test_main_report_prints_each_key_with_bets_and_writes_the_json(vb, capsys):
    recs = [
        brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 481, [[0.95, 100.0]], [[0.96, 500.0]]),            # cp 9
        brec("gemini", "15m", BTC15, T0, T0 + 900, T0 + 541, [[0.95, 100.0]], [[0.96, 500.0]]),            # cp 10
        brec("gemini", "5m", ETH05, T0, T0 + 300, T0 + 161, [[0.03, 400.0]], [[0.05, 50.0]], coin="ETH"),  # NO, cp 9
        brec("pmus", "15m", P15, T0, T0 + 900, T0 + 485, [[0.91, 100.0]], [[0.93, 200.0]]),                # cp 9
        brec("pmus", "1h", P1H, T0 - 2700, T0 + 900, T0 - 700, [[0.55, 10.0]], [[0.60, 10.0]]),            # no bet
    ]
    results = [res("gemini", BTC15, True), res("gemini", ETH05, False), res("pmus", P15, True)]
    Path(vb.OUT).write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    Path(vb.RESULTS).write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    vb.main(["report"])
    out = capsys.readouterr().out

    want = vb.summarise(vb.rows(recs), {r["sym"]: r for r in results})
    with_bets = {k for k, s in want.items() if s["bets"]}
    assert with_bets == {("gemini", "15m", 9), ("gemini", "15m", 10), ("gemini", "5m", 9), ("pmus", "15m", 9)}

    printed = [(m[1], m[2], int(m[3])) for m in re.finditer(r"(?m)^\s*(gemini|pmus)\s+(5m|15m|1h)\s+(\d+)\b", out)]
    assert sorted(printed) == sorted(with_bets), out
    groups = [k[:2] for k in printed]
    assert all(g not in groups[:i] or groups[i - 1] == g for i, g in enumerate(groups)), "a family's lines apart"
    for g in set(groups):
        cps = [k[2] for k in printed if k[:2] == g]
        assert cps == sorted(cps)

    report = json.loads(Path("venue_books_report.json").read_text(encoding="utf-8"))
    assert isinstance(report, list)
    got = {(e["v"], e["fam"], e["cp"]): e for e in report}
    assert len(got) == len(report) and with_bets <= set(got) <= set(want)
    for k, e in got.items():
        assert {x: y for x, y in e.items() if x not in ("v", "fam", "cp")} == json.loads(json.dumps(want[k])), k
