"""thin_report.py: the recorder's verdict, held to the pass marks in RECORDER_PREREG.md.

Offline: Kalshi is a fake `fetch`, files are written to tmp_path. The contract:

- lines(folder, prefix) reads prefix-<day>.jsonl and .jsonl.gz in day order, skipping lines cut short.
- asks(book, side) are the offers to buy `side`, cheapest first: the other side's bids, a bid at p being an ask at
  1 - p. cost_in(book, side) is (cheapest offer, dollars offered up to NEAR above it), None with no offer.
- band(yes_price) is ("yes", p) for 0.80 <= p < 0.90, ("no", 1 - p) for 0.10 < p <= 0.20, else None.
- nearest(snaps, t) is the (at, book) closest to t within WINDOW seconds; vol_at(listing, t) the volume of the last
  listing line at or before t.
- settle(tickers, cache, fetch) asks Kalshi once per settled market (unsettled ones are asked again next time); the
  checkpoint trade (the last at or before close - CHECK) is fetched only for thin markets, from /markets/trades, else
  /historical/trades.
- rows() makes one row per settled market; a qualifying market whose book has no offer on the favourite's side
  counts as an infinite extra cost and $0 on offer (RECORDER_PREREG.md, Changes).
- verdict() applies the three pass marks to No favourites; under NEED of them it is "not enough data".

    python -m pytest research/thin_favourites/tests -q
"""
import gzip
import math
from datetime import datetime, timezone

import pytest

import thin_report as tr

CLOSE = 1_793_100_000
CP = CLOSE - 3600


def book(yes=(), no=()):
    side = lambda levels: [[f"{p:.4f}", f"{s:.2f}"] for p, s in sorted(levels)]
    return {"yes_dollars": side(yes), "no_dollars": side(no)}


def test_lines_reads_plain_and_gzip_in_day_order(tmp_path):
    with gzip.open(tmp_path / "books-2026-10-27.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write('{"n":1}\n{"n":2}\n')
    (tmp_path / "books-2026-10-28.jsonl").write_text('{"n":3}\n{"n":\n{"n":4}\n', encoding="utf-8")
    (tmp_path / "markets-2026-10-27.jsonl").write_text('{"n":99}\n', encoding="utf-8")
    assert [x["n"] for x in tr.lines(str(tmp_path), "books")] == [1, 2, 3, 4]


def test_asks_and_cost_in():
    b = book(yes=[(0.10, 50), (0.12, 30)], no=[(0.85, 10)])
    assert tr.asks(b, "no") == [(0.88, 30.0), (0.90, 50.0)]
    assert tr.asks(b, "yes") == [(0.15, 10.0)]
    best, dollars = tr.cost_in(b, "no")
    assert best == pytest.approx(0.88) and dollars == pytest.approx(0.88 * 30)   # 0.90 is over a cent away
    assert tr.cost_in(book(no=[(0.85, 10)]), "no") is None


@pytest.mark.parametrize("p, want", [
    (0.80, ("yes", 0.80)), (0.8999, ("yes", 0.8999)), (0.90, None), (0.79, None),
    (0.20, ("no", 0.80)), (0.15, ("no", 0.85)), (0.10, None), (0.5, None)])
def test_band(p, want):
    got = tr.band(p)
    if want is None:
        assert got is None
    else:
        assert got[0] == want[0] and got[1] == pytest.approx(want[1])


def test_nearest_and_vol_at():
    snaps = [(CP - 700, "a"), (CP - 200, "b"), (CP + 150, "c")]
    assert tr.nearest(snaps, CP) == (CP + 150, "c")
    assert tr.nearest([(CP - 601, "a")], CP) is None
    assert tr.nearest([], CP) is None
    listing = [{"at": CP - 900, "v": 10.0}, {"at": CP - 10, "v": 50.0}, {"at": CP + 5, "v": 90.0}]
    assert tr.vol_at(listing, CP) == 50.0
    assert tr.vol_at(listing, CP - 1000) is None


def market(t, result="no", vol="5000.00", close=CLOSE, occ=CLOSE - 9000):
    iso = lambda x: datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"ticker": t, "result": result, "volume_fp": vol, "close_time": iso(close),
            "occurrence_datetime": iso(occ), "status": "finalized"}


def test_settle_asks_once_and_only_trades_for_thin(tmp_path):
    cache = str(tmp_path / "settled.json")
    asked = []
    known = {"THIN-1": market("THIN-1"), "THICK-1": market("THICK-1", vol="50000.00"),
             "OPEN-1": {"ticker": "OPEN-1", "result": "", "status": "active"}}
    archived = {"/historical/markets/OLD-1": {"market": market("OLD-1")}}   # too old for /markets

    def fetch(path, params=None):
        params = params or {}
        asked.append((path, params.get("tickers") or params.get("ticker")))
        if path == "/markets":
            assert params["limit"] >= len(params["tickers"].split(","))
            return {"markets": [known[t] for t in params["tickers"].split(",") if t in known]}
        if path == "/markets/trades":
            if params["ticker"] == "OLD-1":
                return {"trades": []}
            assert params["max_ts"] == CP and params["limit"] == 1
            return {"trades": [{"yes_price_dollars": "0.1500", "taker_side": "no", "created_time": "2026-10-28T00:00:00Z"}]}
        if path == "/historical/trades":
            return {"trades": [{"yes_price_dollars": "0.1200", "taker_side": "yes", "created_time": "2026-10-28T00:00:00Z"}]}
        return archived.get(path)

    got = tr.settle(["THIN-1", "THICK-1", "OPEN-1", "OLD-1", "GONE-1"], cache, fetch)
    assert set(got) == {"THIN-1", "THICK-1", "OLD-1"}
    assert got["THIN-1"]["cp_yes"] == pytest.approx(0.15) and got["THIN-1"]["cp_taker"] == "no"
    assert got["THIN-1"]["vol"] == 5000.0 and got["THIN-1"]["close"] == CLOSE and got["THIN-1"]["result"] == "no"
    assert got["THICK-1"]["cp_yes"] is None
    assert got["OLD-1"]["cp_yes"] == pytest.approx(0.12)                     # from the historical tape
    assert ("/markets/trades", "THICK-1") not in asked
    assert sum(p == "/markets" for p, _ in asked) == 1                       # one batch for all five
    asked.clear()
    again = tr.settle(["THIN-1", "THICK-1", "OPEN-1", "OLD-1"], cache, fetch)
    assert set(again) == set(got)
    assert asked == [("/markets", "OPEN-1")]                                 # only the unsettled one again


def test_settle_batches_by_100(tmp_path):
    sizes = []

    def fetch(path, params=None):
        if path == "/markets":
            sizes.append(len(params["tickers"].split(",")))
            return {"markets": [market(t, vol="50000.00") for t in params["tickers"].split(",")]}
        return None
    got = tr.settle([f"T-{i}" for i in range(250)], str(tmp_path / "s.json"), fetch)
    assert sizes == [100, 100, 50] and len(got) == 250


def settled(t, cp_yes, result="no", vol=5000.0, occ=CLOSE - 9000):
    return {"result": result, "vol": vol, "close": CLOSE, "occ": occ, "cp_yes": cp_yes, "cp_taker": "no", "cp_at": CP}


def make(n_no, extra=0.02, size=40, early_vol=1000.0, result="no", series="KXNBASPREAD"):
    """n_no thin No favourites at 85c whose book offers No at 0.85 + extra."""
    st, books, listing = {}, {}, {}
    for i in range(n_no):
        t = f"{series}-E{i}-X"
        st[t] = settled(t, 0.15, result=result)
        bid = round(1 - (0.85 + extra), 4)
        books[t] = [(CP + 60, book(yes=[(bid, size)]))]
        listing[t] = [{"at": CP - 300, "v": early_vol, "s": series}]
    return st, books, listing


def test_verdict_pass():
    st, books, listing = make(100)
    v = tr.verdict(tr.rows(st, books, listing))
    assert v["no"]["n"] == 100
    assert v["no"]["extra"] == pytest.approx(0.02) and v["no"]["dollars"] == pytest.approx(0.87 * 40)
    assert v["early"]["share"] == 1.0
    assert v["pass"] == {"cost": True, "money": True, "early": True} and v["verdict"] == "pass"


def test_verdict_not_enough_data():
    st, books, listing = make(99)
    assert tr.verdict(tr.rows(st, books, listing))["verdict"] == "not enough data"


def test_verdict_fails_on_cost_or_money():
    st, books, listing = make(100, extra=0.04)
    v = tr.verdict(tr.rows(st, books, listing))
    assert v["pass"]["cost"] is False and v["verdict"] == "fail"
    st, books, listing = make(100, size=10)
    v = tr.verdict(tr.rows(st, books, listing))
    assert v["pass"]["money"] is False and v["verdict"] == "fail"


def test_no_offer_counts_as_infinite_cost():
    st, books, listing = make(3)
    t = next(iter(st))
    books[t] = [(CP + 60, book(no=[(0.85, 10)]))]          # nothing offered on the No side
    rows = {r["t"]: r for r in tr.rows(st, books, listing)}
    assert math.isinf(rows[t]["extra"]) and rows[t]["dollars"] == 0.0 and rows[t]["qualifies"]


def test_rows_leave_out_what_does_not_qualify():
    st, books, listing = make(1)
    t = next(iter(st))
    st["THICK-1"] = settled("THICK-1", 0.15, vol=50000.0)        # not thin
    st["MID-1"] = settled("MID-1", 0.50)                         # not in the band
    st["NOBOOK-1"] = settled("NOBOOK-1", 0.15)                   # no book near the checkpoint
    books["NOBOOK-1"] = [(CP - 900, book(yes=[(0.14, 50)]))]
    st["NOTRADE-1"] = settled("NOTRADE-1", None)                 # no trade before the checkpoint
    q = {r["t"] for r in tr.rows(st, books, listing) if r["qualifies"]}
    assert q == {t}


def test_early_thin_share():
    st, books, listing = make(4)
    ts = list(st)
    st[ts[0]]["vol"] = 30000.0                                   # looked thin early, ended thick
    listing[ts[1]] = [{"at": CP - 300, "v": 25000.0}]            # did not look thin early: left out
    listing[ts[2]] = []                                          # no listing before the checkpoint: left out
    v = tr.verdict(tr.rows(st, books, listing))
    assert v["early"]["n"] == 2 and v["early"]["share"] == pytest.approx(0.5)


def test_win_rate_and_sport():
    st, books, listing = make(2, result="yes", series="KXITFMATCH")
    rows = [r for r in tr.rows(st, books, listing) if r["qualifies"]]
    assert all(r["sport"] == "tennis" and r["won"] is False for r in rows)
    assert tr.sport("KXNBATOTAL") == "NBA" and tr.sport("KXNCAAMBGAME") == "college basketball"


def test_lateness_from_the_log():
    log = ("2026-10-27 01:13:22Z  900 books, 0 failed since the last listing; 2052 open, 1153 hot; most late 1.5x its interval\n"
           "2026-10-27 03:03:55Z  recording 10 series to data until 2026-11-09 21:42:55Z\n"
           "2026-10-27 03:09:22Z  900 books, 0 failed since the last listing; 2052 open, 1153 hot; most late 2.0x its interval\n")
    assert tr.lateness(log) == [1.5, 2.0]
