"""thin_books.py: two weeks of order books in thin sports markets (RECORDER_PLAN.md, pass marks RECORDER_PREREG.md).

Everything here is offline: Kalshi is faked (thin_books.get or open_markets monkeypatched, or requests.Session.get
under get() itself), the clock and sleep are injected, and conftest's guard makes any real connection fail the test.

The contract these tests hold it to:

- parse(raw, series) reads one Kalshi market: vol, last, yb, ya as floats (Kalshi sends strings), occ and close as
  unix seconds (occ None without an occurrence time).
- fav(m) is the favourite's price: from the YES bid/ask middle when both sides quote (bid > 0, ask < 1), else from the
  last trade, else None. A YES middle of 0.12 is a No favourite at 0.88.
- A market is live from an hour before its occurrence time to five hours after, or when its volume grew since the last
  listing. It is checked every HOT seconds when live or when its favourite is priced inside BAND, else every COLD.
- due() returns the markets whose time has come, never-checked first, then the most late for their interval first,
  at most `limit` of them.
- top(book) keeps each side's DEPTH highest bids (Kalshi sends them lowest first) in Kalshi's order.
- changes(old, new, at) gives a listing line for each new or changed market and a "gone" line for each that left.
- rotate(folder, today) gzips each day file (name ending -YYYY-MM-DD.jsonl) older than `today` and removes the plain one.
- get() is depth_books.get without the quiet seconds: 404 is None, 429/5xx/connection errors are retried TRIES times
  in all and then raise, and requests are at least 1/RATE apart.
- record() writes books to books-<UTC day>.jsonl and listing lines to markets-<UTC day>.jsonl in `folder`, logs to
  LOG there, never sleeps more than 5 s at a time, re-lists every REFRESH seconds, and rotates at the UTC day change.
  A book that fails is logged with its ticker, leaves no line, and waits for its next interval.

    python -m pytest research/thin_favourites/tests -q
"""
import gzip
import json
import time
from datetime import datetime, timezone

import pytest
import requests

import thin_books as tb

UTC = timezone.utc
T0 = int(datetime(2026, 10, 29, 12, 0, tzinfo=UTC).timestamp())


def raw(ticker, vol="0.00", last="0.0000", yb="0.0000", ya="1.0000", occ="2026-10-29T23:00:00Z", event=None):
    return {"ticker": ticker, "event_ticker": event or ticker.rsplit("-", 1)[0], "volume_fp": vol,
            "last_price_dollars": last, "yes_bid_dollars": yb, "yes_ask_dollars": ya, "occurrence_datetime": occ,
            "close_time": "2026-11-05T23:00:00Z", "status": "active"}


def mk(ticker="KXNBASPREAD-26OCT29AB-A5", **kw):
    m = {"ticker": ticker, "series": "KXNBASPREAD", "event": ticker.rsplit("-", 1)[0], "vol": 100.0, "last": 0.5,
         "yb": 0.49, "ya": 0.51, "occ": T0 + 86400, "close": T0 + 7 * 86400, "grew": False}
    m.update(kw)
    return m


def book(yes=(), no=()):
    side = lambda levels: [[f"{p:.4f}", f"{s:.2f}"] for p, s in sorted(levels)]
    return {"yes_dollars": side(yes), "no_dollars": side(no)}


# ------------------------------------------------------------------ reading markets


def test_parse_reads_kalshis_strings():
    m = tb.parse(raw("KXNBASPREAD-26OCT29AB-A5", vol="1234.00", last="0.8300", yb="0.8200", ya="0.8500"),
                 "KXNBASPREAD")
    assert m["ticker"] == "KXNBASPREAD-26OCT29AB-A5" and m["series"] == "KXNBASPREAD"
    assert m["event"] == "KXNBASPREAD-26OCT29AB"
    assert (m["vol"], m["last"], m["yb"], m["ya"]) == (1234.0, 0.83, 0.82, 0.85)
    assert m["occ"] == int(datetime(2026, 10, 29, 23, tzinfo=UTC).timestamp())
    assert m["close"] == int(datetime(2026, 11, 5, 23, tzinfo=UTC).timestamp())


def test_parse_without_occurrence_time():
    assert tb.parse(raw("X-1", occ=None), "X")["occ"] is None
    assert tb.parse(raw("X-1", occ=""), "X")["occ"] is None


@pytest.mark.parametrize("yb, ya, last, want", [
    (0.80, 0.84, 0.0, 0.82),     # Yes favourite, from the middle
    (0.10, 0.14, 0.0, 0.88),     # No favourite: YES middle 0.12
    (0.0, 1.0, 0.15, 0.85),      # no quotes: the last trade
    (0.0, 0.30, 0.85, 0.85),     # one side only: the last trade
    (0.0, 1.0, 0.0, None),       # nothing at all
])
def test_fav(yb, ya, last, want):
    got = tb.fav(mk(yb=yb, ya=ya, last=last))
    assert got == pytest.approx(want) if want is not None else got is None


# ------------------------------------------------------------------ schedule


def test_live_window_around_the_occurrence_time():
    occ = T0
    assert not tb.live(mk(occ=occ), occ - 3601)
    assert tb.live(mk(occ=occ), occ - 3600)
    assert tb.live(mk(occ=occ), occ + 5 * 3600)
    assert not tb.live(mk(occ=occ), occ + 5 * 3600 + 1)
    assert not tb.live(mk(occ=None), occ)
    assert tb.live(mk(occ=None, grew=True), occ)


def test_interval():
    far = T0 - 86400   # a day before the game
    assert tb.interval(mk(yb=0.80, ya=0.84), far) == tb.HOT            # priced in the band
    assert tb.interval(mk(yb=0.10, ya=0.14), far) == tb.HOT            # No favourite in the band
    assert tb.interval(mk(occ=far + 600), far) == tb.HOT               # the game is on
    assert tb.interval(mk(), far) == tb.COLD                           # neither
    assert tb.interval(mk(yb=0.96, ya=0.98), far) == tb.COLD           # past the band


def test_due_orders_and_limits():
    now = T0
    hot = mk("H-1", yb=0.80, ya=0.84, occ=None)      # HOT, last checked 600 s ago: 2x late
    hot2 = mk("H-2", yb=0.80, ya=0.84, occ=None)     # HOT, 330 s ago: 1.1x late
    cold = mk("C-1", occ=None)                       # COLD, 1900 s ago: 1.06x late
    fresh = mk("C-2", occ=None)                      # COLD, 100 s ago: not due
    new = mk("N-1", occ=None)                        # never checked: first
    markets = {m["ticker"]: m for m in (hot, hot2, cold, fresh, new)}
    last = {"H-1": now - 600, "H-2": now - 330, "C-1": now - 1900, "C-2": now - 100}
    assert [m["ticker"] for m in tb.due(markets, last, now)] == ["N-1", "H-1", "H-2", "C-1"]
    assert [m["ticker"] for m in tb.due(markets, last, now, limit=2)] == ["N-1", "H-1"]


# ------------------------------------------------------------------ books and listing lines


def test_top_keeps_each_sides_best_levels():
    b = book(yes=[(0.01 * i, 10) for i in range(1, 16)], no=[(0.5, 3)])
    t = tb.top(b, 10)
    assert [p for p, _ in t["yes_dollars"]] == [f"{0.01 * i:.4f}" for i in range(6, 16)]
    assert t["no_dollars"] == [["0.5000", "3.00"]]
    assert tb.top({"yes_dollars": None, "no_dollars": []}, 10) == {"yes_dollars": [], "no_dollars": []}


def test_changes_lines_for_new_changed_and_gone():
    a, b, c = mk("A-1"), mk("B-1"), mk("C-1")
    old = {"A-1": a, "B-1": b}
    new = {"A-1": dict(a), "B-1": dict(b, vol=150.0), "C-1": c}
    lines = tb.changes(old, new, 123.0)
    by = {(x["k"], x["t"]) for x in lines}
    assert by == {("m", "B-1"), ("m", "C-1")}                    # A unchanged: no line
    line = next(x for x in lines if x["t"] == "B-1")
    assert (line["at"], line["v"], line["lp"], line["yb"], line["ya"]) == (123.0, 150.0, 0.5, 0.49, 0.51)
    assert line["e"] == b["event"] and line["s"] == b["series"] and line["occ"] == b["occ"]
    gone = tb.changes({"A-1": a}, {}, 9.0)
    assert gone == [{"k": "gone", "t": "A-1", "at": 9.0}]


def test_mark_growth():
    old = {"A-1": mk("A-1", vol=100.0), "B-1": mk("B-1", vol=100.0)}
    new = {"A-1": mk("A-1", vol=120.0), "B-1": mk("B-1", vol=100.0), "C-1": mk("C-1", vol=5.0)}
    tb.mark_growth(old, new)
    assert (new["A-1"]["grew"], new["B-1"]["grew"], new["C-1"]["grew"]) == (True, False, False)


def test_rotate_gzips_past_days_only(tmp_path):
    (tmp_path / "books-2026-10-28.jsonl").write_text('{"a":1}\n', encoding="utf-8")
    (tmp_path / "markets-2026-10-28.jsonl").write_text('{"b":2}\n', encoding="utf-8")
    (tmp_path / "books-2026-10-29.jsonl").write_text('{"c":3}\n', encoding="utf-8")
    done = tb.rotate(str(tmp_path), "2026-10-29")
    assert sorted(done) == ["books-2026-10-28.jsonl", "markets-2026-10-28.jsonl"]
    assert not (tmp_path / "books-2026-10-28.jsonl").exists()
    with gzip.open(tmp_path / "books-2026-10-28.jsonl.gz", "rt", encoding="utf-8") as fh:
        assert fh.read() == '{"a":1}\n'
    assert (tmp_path / "books-2026-10-29.jsonl").exists()


# ------------------------------------------------------------------ Kalshi


class Resp:
    def __init__(self, code, body=None):
        self.status_code, self.body = code, body

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


@pytest.fixture
def clock(monkeypatch):
    """A fake clock under get(): time.time reads it, time.sleep moves it."""
    t = [float(T0)]
    monkeypatch.setattr(time, "time", lambda: t[0])
    monkeypatch.setattr(time, "sleep", lambda s: t.__setitem__(0, t[0] + s))
    monkeypatch.setattr(tb, "_next", [0.0])
    return t


def fake_session(monkeypatch, replies):
    calls = []

    def fake_get(self, url, params=None, timeout=None):
        calls.append((url, params, time.time()))
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(requests.Session, "get", fake_get)
    return calls


def test_get_404_is_none(monkeypatch, clock):
    calls = fake_session(monkeypatch, [Resp(404)])
    assert tb.get("/markets/X") is None
    assert len(calls) == 1 and calls[0][0] == tb.BASE + "/markets/X"


def test_get_retries_then_answers(monkeypatch, clock):
    calls = fake_session(monkeypatch, [Resp(429), Resp(503), requests.ConnectionError("x"), Resp(200, {"ok": 1})])
    assert tb.get("/markets", {"a": 1}) == {"ok": 1}
    assert len(calls) == 4 and calls[-1][1] == {"a": 1}


def test_get_gives_up(monkeypatch, clock):
    fake_session(monkeypatch, [Resp(500)] * tb.TRIES)
    with pytest.raises(RuntimeError, match="gave up"):
        tb.get("/markets")


def test_get_spaces_requests(monkeypatch, clock):
    calls = fake_session(monkeypatch, [Resp(200, {}), Resp(200, {}), Resp(200, {})])
    for _ in range(3):
        tb.get("/x")
    gaps = [b[2] - a[2] for a, b in zip(calls, calls[1:])]
    assert all(g >= 1 / tb.RATE - 1e-6 for g in gaps)   # unix-time floats hold about 0.2 microseconds


def test_open_markets_pages_through_every_series(monkeypatch):
    pages = {(tb.SERIES[0], None): {"markets": [raw(f"{tb.SERIES[0]}-E-1")], "cursor": "c2"},
             (tb.SERIES[0], "c2"): {"markets": [raw(f"{tb.SERIES[0]}-E-2")], "cursor": ""}}
    asked = []

    def fake_get(path, params=None):
        asked.append((params["series_ticker"], params.get("cursor")))
        assert path == "/markets" and params["status"] == "open"
        return pages.get((params["series_ticker"], params.get("cursor")), {"markets": [], "cursor": None})
    monkeypatch.setattr(tb, "get", fake_get)
    got = tb.open_markets()
    assert set(got) == {f"{tb.SERIES[0]}-E-1", f"{tb.SERIES[0]}-E-2"}
    assert got[f"{tb.SERIES[0]}-E-1"]["series"] == tb.SERIES[0]
    assert {s for s, _ in asked} == set(tb.SERIES)


# ------------------------------------------------------------------ the recording loop


def read_lines(folder, prefix):
    out = []
    for p in sorted(folder.glob(f"{prefix}-*.jsonl")):
        out += [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    for p in sorted(folder.glob(f"{prefix}-*.jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            out += [json.loads(x) for x in fh.read().splitlines()]
    return out


@pytest.fixture
def loop(monkeypatch):
    """Fake clock and sleep for record(), plus fakes for the listing and the books."""
    t = [float(T0)]
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        t[0] += s
    monkeypatch.setattr(time, "sleep", lambda s: pytest.fail("record() must use its injected sleep"))
    return {"now": lambda: t[0], "sleep": sleep, "t": t, "sleeps": sleeps}


def test_record_books_listing_gone_and_failures(monkeypatch, tmp_path, loop):
    hot = mk("HOT-1", yb=0.80, ya=0.84, occ=None)
    cold = mk("COLD-1", occ=None)
    listings = [{"HOT-1": hot, "COLD-1": cold}, {"HOT-1": dict(hot, vol=150.0)}]   # COLD-1 leaves at the 2nd

    def fake_open():
        return {k: dict(v) for k, v in (listings.pop(0) if len(listings) > 1 else listings[0]).items()}
    monkeypatch.setattr(tb, "open_markets", fake_open)
    asked = []

    def fake_get(path, params=None):
        asked.append((path, params, loop["now"]()))
        if "COLD-1" in path:
            raise RuntimeError("boom")
        return {"orderbook_fp": book(yes=[(0.80, 5)], no=[(0.16, 7)])}
    monkeypatch.setattr(tb, "get", fake_get)

    tb.record(until=T0 + 650, now=loop["now"], sleep=loop["sleep"], folder=str(tmp_path))

    books = read_lines(tmp_path, "books")
    assert [b["t"] for b in books] == ["HOT-1", "HOT-1", "HOT-1"]            # at 0, 300 and 600 s
    assert books[0]["book"] == book(yes=[(0.80, 5)], no=[(0.16, 7)])
    assert books[0]["s"] == "KXNBASPREAD" and books[0]["e"] == hot["event"]
    assert all(p[1] == {"depth": tb.DEPTH} for p in asked)
    assert sum("COLD-1" in p[0] for p in asked) == 1                         # failed once, not retried at once
    lines = read_lines(tmp_path, "markets")
    assert {(x["k"], x["t"]) for x in lines} == {("m", "HOT-1"), ("m", "COLD-1"), ("gone", "COLD-1")}
    log = (tmp_path / tb.LOG).read_text(encoding="utf-8")
    assert "COLD-1" in log and "boom" in log
    assert max(loop["sleeps"]) <= 5.0


def test_record_rotates_at_the_utc_day_change(monkeypatch, tmp_path, loop):
    start = int(datetime(2026, 10, 29, 23, 58, tzinfo=UTC).timestamp())
    loop["t"][0] = float(start)
    m = mk("HOT-1", yb=0.80, ya=0.84, occ=None)
    monkeypatch.setattr(tb, "open_markets", lambda: {"HOT-1": dict(m)})
    monkeypatch.setattr(tb, "get", lambda path, params=None: {"orderbook_fp": book(yes=[(0.80, 5)])})
    tb.record(until=start + 400, now=loop["now"], sleep=loop["sleep"], folder=str(tmp_path))
    assert (tmp_path / "books-2026-10-29.jsonl.gz").exists()
    assert not (tmp_path / "books-2026-10-29.jsonl").exists()
    assert (tmp_path / "books-2026-10-30.jsonl").exists()
    assert len(read_lines(tmp_path, "books")) == 2                            # at 23:58 and 00:03


def test_record_keeps_the_last_list_when_listing_fails(monkeypatch, tmp_path, loop):
    m = mk("HOT-1", yb=0.80, ya=0.84, occ=None)
    replies = [{"HOT-1": dict(m)}, RuntimeError("down")]

    def fake_open():
        r = replies.pop(0) if replies else {"HOT-1": dict(m)}
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(tb, "open_markets", fake_open)
    monkeypatch.setattr(tb, "get", lambda path, params=None: {"orderbook_fp": book(yes=[(0.80, 5)])})
    tb.record(until=T0 + 350, now=loop["now"], sleep=loop["sleep"], folder=str(tmp_path))
    assert len(read_lines(tmp_path, "books")) == 2                            # still checked at 300 s
    assert not any(x["k"] == "gone" for x in read_lines(tmp_path, "markets"))
    assert "down" in (tmp_path / tb.LOG).read_text(encoding="utf-8")


# ------------------------------------------------------------------ command line


def test_main_record_days(monkeypatch):
    got = {}
    monkeypatch.setattr(tb, "record", lambda until=None, **kw: got.setdefault("until", until))
    monkeypatch.setattr(time, "time", lambda: float(T0))
    monkeypatch.setattr("sys.argv", ["thin_books.py", "record", "2"])
    tb.main()
    assert got["until"] == pytest.approx(T0 + 2 * 86400)
    got.clear()
    monkeypatch.setattr("sys.argv", ["thin_books.py", "record"])
    tb.main()
    assert got["until"] == pytest.approx(T0 + tb.DAYS * 86400)
    monkeypatch.setattr("sys.argv", ["thin_books.py", "nonsense"])
    with pytest.raises(SystemExit):
        tb.main()
