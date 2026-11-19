"""depth_tape.py: the historical half of the depth check, from Kalshi's public trade tape.

Four groups of other markets passed the plan's test (other_markets_findings.md): hourly temperature at 10 and 30
minutes before the close, and daily economics (AAA gas, SOFR, ERCOT peak) at 1 and 2 hours. The backtest assumed a
full $10 filled at the recorded ask + 0.4c. The tape (who bought what, at what price, when) says whether that much
ever traded on our side at that price soon after the checkpoint. What's pinned:

- bets_from() picks the same bets as other_markets.bets() and groups() (compared on a seeded mix of rows written to
  the files other_markets.load() reads), keeping only the liquid ones in the four passed groups;
- the tape is read from our side: a NO buyer's price is 1 - the YES price, and only takers who bought our side count;
- the windows: from the checkpoint (inclusive) to 60 s / 5 min after it for an hourly market, 10 / 30 min for a daily
  one (exclusive), at our price up to the ask + 0.4c;
- $10 and up in the window is a full fill (exactly $10 counts); profits are other_markets' assumption and the capped
  one (only what traded); the summary splits the halves at SPLIT, Sep 1, by close;
- fetch() never touches the network here: dt.get is faked, and every socket connect is refused, so a request the
  fake missed fails the test instead of reaching Kalshi.

Readings of the spec (where it leaves a choice, these tests pin one):

1. check(bet, trades) returns the bet's own fields plus soon, win, any_win, first, full10, pnl_backtest and
   pnl_capped; summarise() takes a list of those (it needs each one's key and close).
2. soon and win are (contracts, dollars) tuples, counting only takers who bought our side at our price <= ask + SLIP
   (+1e-9), from cp inclusive to cp + WINDOW[unit][0] (soon) or [1] (win) exclusive. any_win is True when any taker
   bought our side in the win window [cp, cp + WINDOW[unit][1]) at any price.
3. check()["first"] is first(trades, side, cp): measured from the checkpoint, at any price and with no end, so a
   trade after the window still counts. first() returns a (seconds, price) tuple, or None.
4. full10 is win dollars >= STAKE (exactly $10 is full). summarise()'s soon10 is the share with soon dollars >= STAKE.
5. summarise(): close < SPLIT is "before", close >= SPLIT "after", "all" both; any_win, soon10 and full10 are
   fractions of the group's bets; median_win_dollars is statistics.median of the win dollars (the mean of the middle
   two for an even count); pnl_backtest and pnl_capped are means over all the group's bets; pnl_full10_only is the
   mean pnl_backtest over the full10 bets, None if none (for a full bet pnl_capped is the same number and the tests
   build them so, so reading it from pnl_capped passes too); capped_total is the sum of pnl_capped. A (key, half)
   with no bets is left out, so summarise([]) == {}.
6. bets_from(): each dict carries at least the ten listed fields; side is "yes"/"no" as in other_markets; ask is the
   favourite's cost (YES: the YES ask; NO: round(1 - YES bid, 4)); mult is a float; close and cp are unix seconds
   (int or float); the 3c screen is other_markets' own `a - b <= 0.03` with no tolerance, so a 95c/98c quote (whose
   difference floats to 0.030000000000000027) is out there and here. The order of the bets isn't pinned.
7. tape_bets() reads other_markets.json and other_hours.csv from the working directory (other_markets.load()).
8. fetch() makes every request through the module's own get(url, params) (a path or a full URL; the fake matches
   the ending), so faking dt.get is the whole network, and pacing lives inside get. The cutoff is
   /historical/cutoff's market_settled_ts, an ISO string. A market closing days after it asks /markets/trades first,
   days before it /historical/trades first (a close right at the cutoff isn't pinned). "Empty" means no trades over
   every page, and a None (404) answer counts as empty; only then is the other endpoint asked. Every trades request
   carries ticker, min_ts = close - SPAN[unit] and max_ts = close + 60 (limit isn't pinned). One line per ticker, even
   when two bets share it; a ticker with no trades on either endpoint still gets its line, with tr [] (as in the tape
   file being filled now), so it isn't asked again. Lines are exactly {"t", "tr"}; rows are [ts (unix seconds, to the
   millisecond is enough), YES price, contracts, taker side], ascending by ts. fetch() appends and leaves the lines
   already there untouched. Its default path is TAPE.
9. main() reads sys.argv. "fetch" runs fetch() once on TAPE. With no argument it reads TAPE from the working
   directory, checks each tape_bets() bet against its ticker's line (a line with tr [] is a bet checked with no
   trades), leaves out bets whose ticker has no line and prints how many bets (not tickers) that was, then prints
   summarise() of the rest. The report makes no request.
10. ours() returns (ts, price, contracts) tuples in tape order; ours/seen/first take tape rows as lists (read from
    JSON) or tuples.
"""

from __future__ import annotations

import csv
import importlib
import inspect
import json
import random
import re
import socket
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

UTC = timezone.utc
TEMP_10 = ("Climate and Weather", "hourly", "10min")
TEMP_30 = ("Climate and Weather", "hourly", "30min")
ECON_1 = ("Economics", "daily", "1h")
ECON_2 = ("Economics", "daily", "2h")
PASSED = {TEMP_10, TEMP_30, ECON_1, ECON_2}
FIELDS = ("ticker", "series", "key", "cp", "close", "side", "ask", "won", "mult", "unit")
CSV_FIELDS = (["series", "ticker", "event", "close", "result", "volume", "unit"]
              + [f"{x}{k}" for k in range(61) for x in "ba"])

CLOSE_ISO = "2026-09-20T14:00:00Z"            # a test-half close
SPLIT_ISO = "2026-09-01T00:00:00Z"
CUTOFF_ISO = "2026-08-12T00:00:00Z"           # Kalshi's live/historical cutoff as it stood when the tape was fetched


def ts(when) -> float:
    if isinstance(when, str):
        when = datetime.fromisoformat(when.replace("Z", "+00:00"))
    return when.timestamp()


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


CLOSE = ts(CLOSE_ISO)
SPLIT = ts(SPLIT_ISO)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every socket connect fails: a request the fakes below miss can never reach Kalshi."""
    def refuse(*args, **kwargs):
        raise RuntimeError("a depth_tape test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


@pytest.fixture
def dt(study):
    """depth_tape, imported with the synthetic study folder as the working directory."""
    return importlib.import_module("depth_tape")


# ------------------------------------------------------------------ rows as other_markets.load() yields them


def meta(series, category, frequency, fee_multiplier=1):
    """A series' entry in other_markets.json."""
    return {"series": series, "title": series, "category": category, "frequency": frequency, "fee_type": "quadratic",
            "fee_multiplier": fee_multiplier, "markets": []}


TEMP = meta("KXTEMPNYCH", "Climate and Weather", "hourly")
TEMP_NONE = meta("KXTEMPLAXH", "Climate and Weather", "hourly", None)
GAS = meta("KXAAAGASD", "Economics", "daily", None)
SOFR = meta("KXSOFRD", "Economics", "daily", 0.5)
HIGH = meta("KXHIGHNY", "Climate and Weather", "daily")        # daily weather: not a group that passed
INX = meta("KXINXU", "Financials", "hourly")
ECON_H = meta("KXECONH", "Economics", "hourly")                 # hourly economics: not one either


def row(s, quotes, close=CLOSE_ISO, result="yes", ticker=None, unit=None):
    """A row of other_hours.csv as csv.DictReader yields it, every field a string. quotes: {k: (YES bid, YES ask)}, k
    minutes before the close for an hourly series (unit "min"), hours for a daily one ("hour"); "" where none."""
    r = {"series": s["series"], "ticker": ticker or f"{s['series']}-{close[:13]}", "event": f"{s['series']}-E",
         "close": close, "result": result, "volume": "100",
         "unit": unit or ("min" if s["frequency"] == "hourly" else "hour")}
    for k in range(61):
        r[f"b{k}"] = r[f"a{k}"] = ""
    for k, (b, a) in quotes.items():
        r[f"b{k}"], r[f"a{k}"] = b, a
    return r


def fields(b):
    return {k: b[k] for k in FIELDS}


def write_other(folder, pairs):
    """other_markets.json and other_hours.csv holding these (row, series) pairs, so other_markets.load() yields them."""
    metas = {s["series"]: s for _, s in pairs}
    (folder / "other_markets.json").write_text(json.dumps(list(metas.values())), encoding="utf-8")
    with (folder / "other_hours.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(r for r, _ in pairs)


def random_quote(rng):
    """A YES bid and ask as the candles give them: mostly 90c+ favourites on either side with 0-6c spreads (3c ones
    included, whose differences float to either side of 0.03), some without a favourite, some missing."""
    if rng.random() < 0.06:
        return "", ""
    if rng.random() < 0.15:
        mid = rng.randint(20, 85) / 100
        return str(round(mid - 0.01, 2)), str(round(mid + 0.01, 2))
    price = rng.choice([0.89, 0.9, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 0.995, 0.999, 1.0])
    spread = rng.choice([0.0, 0.01, 0.02, 0.03, 0.03, 0.03, 0.04, 0.06])
    if rng.random() < 0.5:
        a = price
        b = round(a - spread, 3)
    else:
        b = round(1 - price, 3)
        a = round(b + spread, 3)
    return str(b), str(a)


def random_pairs(n=500, seed=12):
    """A seeded mix of markets from passed and other groups, closing 3 hours apart from Jul 19 (across SPLIT)."""
    rng = random.Random(seed)
    mixed = [TEMP, TEMP_NONE, GAS, SOFR, HIGH, INX, ECON_H]
    start = datetime(2026, 7, 19, tzinfo=UTC)
    out = []
    for i in range(n):
        s = mixed[i % len(mixed)]
        close = iso(start + timedelta(hours=3 * i))
        r = row(s, {k: random_quote(rng) for k in range(61)}, close=close, result=rng.choice(["yes", "no"]),
                ticker=f"{s['series']}-{i:04d}")
        out.append((r, s))
    return out


# ------------------------------------------------------------------ constants


def test_the_spec_constants(dt):
    assert len(dt.PASSED) == 4 and set(dt.PASSED) == PASSED
    assert dt.WINDOW == {"min": (60, 300), "hour": (600, 1800)}
    assert dt.STAKE == 10
    assert dt.TAPE == "depth_tape.jsonl"
    assert dt.SPAN == {"min": 35 * 60, "hour": 150 * 60}


# ------------------------------------------------------------------ bets_from


def test_a_liquid_yes_favourite_at_ten_minutes(dt):
    r = row(TEMP, {10: ("0.95", "0.96")}, result="yes")
    (b,) = dt.bets_from([(r, TEMP)])
    assert fields(b) == {"ticker": r["ticker"], "series": "KXTEMPNYCH", "key": TEMP_10, "cp": CLOSE - 600,
                         "close": CLOSE, "side": "yes", "ask": 0.96, "won": True, "mult": 1.0, "unit": "min"}
    (lost,) = dt.bets_from([(row(TEMP, {10: ("0.95", "0.96")}, result="no"), TEMP)])
    assert lost["won"] is False


def test_a_no_favourite_costs_one_minus_the_yes_bid(dt):
    # YES costs 9c, NO costs 1 - 0.07 = 93c (0.9299999999999999 unrounded): NO is the favourite
    r = row(TEMP, {30: ("0.07", "0.09")}, result="no")
    (b,) = dt.bets_from([(r, TEMP)])
    assert fields(b) == {"ticker": r["ticker"], "series": "KXTEMPNYCH", "key": TEMP_30, "cp": CLOSE - 1800,
                         "close": CLOSE, "side": "no", "ask": 0.93, "won": True, "mult": 1.0, "unit": "min"}
    (lost,) = dt.bets_from([(row(TEMP, {30: ("0.07", "0.09")}, result="yes"), TEMP)])
    assert lost["side"] == "no" and lost["won"] is False


def test_an_hourly_market_bets_at_30_and_10_minutes_only(dt):
    good = ("0.97", "0.98")
    r = row(TEMP, {k: good for k in (45, 30, 20, 10, 5)})
    bets = dt.bets_from([(r, TEMP)])
    assert sorted((b["key"], b["cp"]) for b in bets) == sorted([(TEMP_10, CLOSE - 600), (TEMP_30, CLOSE - 1800)])
    assert all(b["ask"] == 0.98 and b["side"] == "yes" and b["close"] == CLOSE for b in bets)


def test_a_daily_market_bets_at_2_and_1_hours_only(dt):
    good = ("0.02", "0.03")          # NO at 98c
    r = row(GAS, {k: good for k in (12, 6, 3, 2, 1)}, result="no")
    bets = dt.bets_from([(r, GAS)])
    assert sorted((b["key"], b["cp"]) for b in bets) == sorted([(ECON_1, CLOSE - 3600), (ECON_2, CLOSE - 7200)])
    assert all(b["unit"] == "hour" and b["side"] == "no" and b["ask"] == 0.98 and b["won"] is True for b in bets)


def test_fee_multiplier_defaults_to_one(dt):
    (none,) = dt.bets_from([(row(GAS, {1: ("0.02", "0.03")}), GAS)])         # fee_multiplier None
    (half,) = dt.bets_from([(row(SOFR, {1: ("0.02", "0.03")}), SOFR)])       # fee_multiplier 0.5
    assert none["mult"] == 1.0 and half["mult"] == 0.5
    assert isinstance(none["mult"], float)


@pytest.mark.parametrize("quote, why", [
    (("0.91", "0.95"), "4c spread"),
    (("0.90", "0.96"), "6c spread"),
    (("0.95", "0.98"), "a 3c spread that floats to 0.030000000000000027, out in other_markets too"),
    (("0.88", "0.89"), "89c, under the band"),
    (("0.99", "1.0"), "no ask under $1"),
    (("0", "0.02"), "no bid above 0"),
    (("", ""), "no quote"),
    (("0.95", ""), "no ask"),
    (("0.40", "0.42"), "no favourite in the band"),
])
def test_bets_the_rule_leaves_out(dt, quote, why):
    assert dt.bets_from([(row(TEMP, {10: quote}), TEMP)]) == [], why


@pytest.mark.parametrize("quote, side, ask", [
    (("0.89", "0.90"), "yes", 0.90),            # LO is in the band
    (("0.998", "0.999"), "yes", 0.999),         # and so is HI
    (("0.92", "0.95"), "yes", 0.95),            # a 3c spread whose difference floats to 0.03 or under
    (("0.03", "0.06"), "no", 0.97),
    (("0.97", "0.97"), "yes", 0.97),            # no spread at all
])
def test_bets_at_the_edges_of_the_rule(dt, quote, side, ask):
    (b,) = dt.bets_from([(row(TEMP, {10: quote}), TEMP)])
    assert (b["side"], b["ask"]) == (side, ask)


def test_the_3c_screen_is_other_markets_own_to_the_last_float(dt):
    quotes = [("0.91", "0.94"), ("0.92", "0.95"), ("0.93", "0.96"), ("0.94", "0.97"), ("0.95", "0.98"),
              ("0.96", "0.99"), ("0.01", "0.04"), ("0.02", "0.05"), ("0.03", "0.06"), ("0.04", "0.07")]
    want = [q for q in quotes if float(q[1]) - float(q[0]) <= 0.03]
    assert 0 < len(want) < len(quotes)          # both sides of the float edge are in the sample
    got = [q for q in quotes if dt.bets_from([(row(TEMP, {10: q}), TEMP)])]
    assert got == want


@pytest.mark.parametrize("s, k", [(HIGH, 1), (HIGH, 2), (ECON_H, 10), (ECON_H, 30), (INX, 10),
                                  (meta("KXHIGHNY", "Climate", "daily"), 1)])
def test_groups_that_did_not_pass_make_no_bets(dt, s, k):
    assert dt.bets_from([(row(s, {k: ("0.97", "0.98")}), s)]) == []


def test_the_synthetic_studys_series_are_not_in_a_passed_group(dt, study):
    assert dt.bets_from(study.other_markets.load()) == []


def test_bets_from_matches_other_markets_group_by_group(dt, study, tmp_path, monkeypatch):
    om = study.other_markets
    write_other(tmp_path, random_pairs())
    monkeypatch.chdir(tmp_path)
    groups = om.groups(om.bets())
    mine = dt.bets_from(om.load())
    counts = Counter(b["key"] for b in mine)
    assert set(counts) <= PASSED
    for key in PASSED:
        assert counts[key] == len(groups[key]) > 20, key
    assert (sorted((b["series"], b["key"], b["close"]) for b in mine)
            == sorted((x[2], (x[0], x[1], x[3]), x[4]) for key in PASSED for x in groups[key]))
    every = Counter((x[0], x[1], x[3]) for x in om.bets())
    assert any(every[key] > len(groups[key]) for key in PASSED)      # some illiquid bets were there to drop


def test_each_bet_profits_as_other_markets_says(dt, study, tmp_path, monkeypatch):
    """won, ask and mult together decide the backtest's profit: check() on an empty tape gives other_markets'."""
    om = study.other_markets
    write_other(tmp_path, random_pairs(n=300, seed=3))
    monkeypatch.chdir(tmp_path)
    theirs = {(x[2], x[3], x[4]): x[5] for key, xs in om.groups(om.bets()).items() if key in PASSED for x in xs}
    mine = dt.bets_from(om.load())
    assert len(mine) == len(theirs) > 50
    for b in mine:
        assert dt.check(b, [])["pnl_backtest"] == pytest.approx(theirs[(b["series"], b["key"][2], b["close"])])


def test_tape_bets_reads_the_other_markets_files(dt, study, tmp_path, monkeypatch):
    pairs = random_pairs(n=120, seed=8)
    write_other(tmp_path, pairs)
    monkeypatch.chdir(tmp_path)
    want = dt.bets_from(study.other_markets.load())
    assert want and dt.tape_bets() == want


# ------------------------------------------------------------------ ours, seen and first

T = ts("2026-09-20T13:50:00Z")
TAPE_ROWS = [[T, 0.95, 10.0, "yes"],
             [T + 1, 0.07, 4.0, "no"],         # a NO buyer at 93c
             [T + 2, 0.96, 2.5, "yes"],
             [T + 3, 0.5, 1.0, "no"],
             [T + 4, 0.04, 6.0, "yes"]]        # a YES buyer at 4c: a longshot buyer, not on a NO favourite's side


def test_ours_keeps_our_sides_buyers_at_our_price(dt):
    assert dt.ours(TAPE_ROWS, "yes") == [(T, 0.95, 10.0), (T + 2, 0.96, 2.5), (T + 4, 0.04, 6.0)]
    assert dt.ours(TAPE_ROWS, "no") == [(T + 1, 0.93, 4.0), (T + 3, 0.5, 1.0)]
    assert dt.ours([tuple(x) for x in TAPE_ROWS], "no") == [(T + 1, 0.93, 4.0), (T + 3, 0.5, 1.0)]
    assert dt.ours([], "yes") == []


def test_seen_adds_contracts_and_dollars_at_our_price(dt):
    c, d = dt.seen(TAPE_ROWS, "yes", 0.96, T, T + 10)
    assert c == pytest.approx(18.5) and d == pytest.approx(0.95 * 10 + 0.96 * 2.5 + 0.04 * 6)
    c, d = dt.seen(TAPE_ROWS, "no", 0.93, T, T + 10)
    assert c == pytest.approx(5.0) and d == pytest.approx(0.93 * 4 + 0.5 * 1)
    assert isinstance(dt.seen(TAPE_ROWS, "no", 0.93, T, T + 10), tuple)


def test_seen_stops_at_the_limit(dt):
    assert dt.seen(TAPE_ROWS, "yes", 0.955, T, T + 3) == pytest.approx((10.0, 9.5))
    assert dt.seen(TAPE_ROWS, "yes", 0.96 - 1e-12, T, T + 3) == pytest.approx((12.5, 11.9))   # within 1e-9 is at it
    assert dt.seen(TAPE_ROWS, "yes", 0.96 - 1e-6, T, T + 3) == pytest.approx((10.0, 9.5))
    assert dt.seen(TAPE_ROWS, "no", 0.92, T, T + 10) == pytest.approx((1.0, 0.5))           # 93c is over 92c
    assert dt.seen(TAPE_ROWS, "no", 0.49, T, T + 10) == (0, 0)


def test_seen_counts_from_t0_up_to_but_not_including_t1(dt):
    assert dt.seen(TAPE_ROWS, "yes", 1.0, T, T + 2) == pytest.approx((10.0, 9.5))
    assert dt.seen(TAPE_ROWS, "yes", 1.0, T, T + 2.001) == pytest.approx((12.5, 11.9))
    assert dt.seen(TAPE_ROWS, "yes", 1.0, T + 0.001, T + 4) == pytest.approx((2.5, 2.4))
    assert dt.seen(TAPE_ROWS, "yes", 1.0, T + 5, T + 50) == (0, 0)
    assert dt.seen([], "yes", 1.0, T, T + 50) == (0, 0)


def test_first_is_the_first_of_our_buyers_from_t0(dt):
    assert dt.first(TAPE_ROWS, "yes", T) == (0.0, 0.95)          # one exactly at t0 counts
    assert dt.first(TAPE_ROWS, "yes", T + 0.5) == (1.5, 0.96)
    assert dt.first(TAPE_ROWS, "no", T) == (1.0, 0.93)           # the other side's earlier buyer is skipped
    assert dt.first(TAPE_ROWS, "no", T + 1.5) == (1.5, 0.5)      # at any price
    assert dt.first(TAPE_ROWS, "no", T + 3.5) is None
    assert dt.first(TAPE_ROWS, "yes", T + 4.5) is None
    assert dt.first([], "yes", T) is None


# ------------------------------------------------------------------ check


def bet(**changes):
    """A bet as bets_from() makes it: by default YES at 95c, 10 minutes before a 14:00 close, won."""
    b = {"ticker": "KXTEMPNYCH-26SEP2014-T71.99", "series": "KXTEMPNYCH", "key": TEMP_10, "cp": CLOSE - 600,
         "close": CLOSE, "side": "yes", "ask": 0.95, "won": True, "mult": 1.0, "unit": "min"}
    b.update(changes)
    return b


def daily(**changes):
    """A daily bet: NO at 97c an hour before the close."""
    b = bet(ticker="KXAAAGASD-26SEP20-3.45", series="KXAAAGASD", key=ECON_1, cp=CLOSE - 3600, side="no",
            ask=0.97, unit="hour")
    b.update(changes)
    return b


def at(b, after, price, contracts, side=None):
    """A tape row `after` seconds past the bet's checkpoint: a taker bought `side` (the bet's own by default) at
    `price` on that side."""
    side = side or b["side"]
    return [b["cp"] + after, price if side == "yes" else round(1 - price, 4), contracts, side]


def backtest(om, ask, won, mult):
    p = min(ask + om.SLIP, 0.999)
    c = 10 / p
    return (c if won else 0) - 10 - om.fee(c, p, mult)


def test_check_keeps_the_bet(dt):
    b = bet()
    out = dt.check(b, [at(b, 5, 0.95, 3)])
    assert {k: out[k] for k in b} == b
    assert {"soon", "win", "any_win", "first", "full10", "pnl_backtest", "pnl_capped"} <= set(out)
    assert isinstance(out["soon"], tuple) and isinstance(out["win"], tuple)


def test_the_hourly_windows_are_one_and_five_minutes(dt):
    b = bet()                                   # YES at 95c: up to 95.4c counts
    tape = [at(b, -1, 0.95, 100),               # before the checkpoint
            at(b, 0, 0.95, 1),                  # soon
            at(b, 30, 0.96, 32),                # too dear
            at(b, 30, 0.95, 64, side="no"),     # the other side
            at(b, 59.5, 0.954, 2),              # soon, at the limit
            at(b, 60, 0.95, 4),                 # the window, not soon
            at(b, 299.5, 0.93, 8),              # the window
            at(b, 300, 0.95, 16)]               # after it
    out = dt.check(b, tape)
    assert out["soon"] == pytest.approx((3, 0.95 + 0.954 * 2))
    assert out["win"] == pytest.approx((15, 0.95 + 0.954 * 2 + 0.95 * 4 + 0.93 * 8))


def test_the_daily_windows_are_ten_and_thirty_minutes(dt):
    b = daily()                                 # NO at 97c: up to 97.4c counts
    tape = [at(b, -0.5, 0.97, 100), at(b, 0, 0.97, 1), at(b, 599, 0.974, 2), at(b, 600, 0.96, 4),
            at(b, 1799, 0.97, 8), at(b, 1800, 0.97, 16), at(b, 100, 0.975, 32), at(b, 100, 0.97, 64, side="yes")]
    out = dt.check(b, tape)
    assert out["soon"] == pytest.approx((3, 0.97 + 0.974 * 2))
    assert out["win"] == pytest.approx((15, 0.97 + 0.974 * 2 + 0.96 * 4 + 0.97 * 8))


def test_a_no_bet_reads_the_tape_from_the_no_side(dt):
    b = bet(side="no", ask=0.93)
    tape = [[b["cp"] + 10, 0.07, 5.0, "no"],      # NO bought at 93c: ours
            [b["cp"] + 20, 0.93, 7.0, "yes"],     # YES bought at 93c: not our side
            [b["cp"] + 30, 0.06, 9.0, "no"]]      # NO bought at 94c: over 93.4c
    out = dt.check(b, tape)
    assert out["soon"] == pytest.approx((5.0, 4.65))
    assert out["win"] == pytest.approx((5.0, 4.65))
    assert out["first"] == (10.0, 0.93)


def test_any_win_is_any_of_our_buyers_in_the_window_at_any_price(dt):
    b = bet()
    pricey = dt.check(b, [at(b, 100, 0.99, 50)])
    assert pricey["any_win"] is True and pricey["win"] == (0, 0) and pricey["full10"] is False
    for tape in ([], [at(b, 300, 0.95, 50)], [at(b, -1, 0.95, 50)], [at(b, 100, 0.95, 50, side="no")]):
        assert dt.check(b, tape)["any_win"] is False
    assert dt.check(b, [at(b, 0, 0.95, 1)])["any_win"] is True
    d = daily()
    assert dt.check(d, [at(d, 1799, 0.99, 1)])["any_win"] is True
    assert dt.check(d, [at(d, 1800, 0.97, 1)])["any_win"] is False


def test_first_is_counted_from_the_checkpoint_at_any_price_and_time(dt):
    b = bet()
    assert dt.check(b, [at(b, -30, 0.95, 5), at(b, 400, 0.99, 1), at(b, 500, 0.95, 5)])["first"] == (400.0, 0.99)
    assert dt.check(b, [at(b, 0, 0.94, 5)])["first"] == (0.0, 0.94)
    assert dt.check(b, [at(b, -30, 0.95, 5), at(b, 50, 0.95, 5, side="no")])["first"] is None
    d = daily()
    assert dt.check(d, [at(d, 2000, 0.97, 1)])["first"] == (2000.0, 0.97)


def test_full10_starts_at_exactly_ten_dollars(dt):
    b = bet()
    assert dt.check(b, [at(b, 10, 0.9375, 8), at(b, 200, 0.625, 4)])["full10"] is True        # $7.50 + $2.50
    assert dt.check(b, [at(b, 10, 0.9375, 8), at(b, 200, 0.625, 3.99)])["full10"] is False    # $9.99375
    assert dt.check(b, [at(b, 10, 0.95, 100)])["full10"] is True
    # $10 and more, but too dear, out of the window or on the other side
    for tape in ([at(b, 10, 0.96, 100)], [at(b, 300, 0.95, 100)], [at(b, -1, 0.95, 100)], [at(b, 10, 0.95, 100, "no")]):
        assert dt.check(b, tape)["full10"] is False


def test_pnl_backtest_is_other_markets_full_ten_dollars(dt, study):
    om = study.other_markets
    assert dt.check(bet(), [])["pnl_backtest"] == pytest.approx(0.44218, abs=1e-5)   # 10 / 0.954 - $10 - 4c fee
    assert dt.check(bet(won=False), [])["pnl_backtest"] == pytest.approx(-10.04)
    for ask, won, mult in ((0.95, True, 1.0), (0.95, False, 1.0), (0.97, True, 0.5), (0.91, False, 0.5),
                           (0.998, True, 1.0), (0.998, False, 1.0)):       # 99.8c + 0.4c is capped at 99.9c
        want = backtest(om, ask, won, mult)
        b = bet(ask=ask, won=won, mult=mult)
        assert dt.check(b, [])["pnl_backtest"] == pytest.approx(want)
        assert dt.check(b, [at(b, 10, ask, 3), at(b, 100, ask, 500)])["pnl_backtest"] == pytest.approx(want)
    d = daily(won=False, mult=0.5)
    assert dt.check(d, [])["pnl_backtest"] == pytest.approx(backtest(om, 0.97, False, 0.5))


def test_pnl_capped_buys_only_what_traded_in_the_window(dt, study):
    om = study.other_markets
    p = 0.954
    b = bet()
    tape = [at(b, 10, 0.95, 2), at(b, 120, 0.95, 3), at(b, 120, 0.99, 50), at(b, 400, 0.95, 50)]   # 5 in the window
    assert dt.check(b, tape)["pnl_capped"] == pytest.approx(5 - 5 * p - om.fee(5, p, 1))
    assert dt.check(bet(won=False), tape)["pnl_capped"] == pytest.approx(-5 * p - om.fee(5, p, 1))
    assert dt.check(bet(mult=0.5), tape)["pnl_capped"] == pytest.approx(5 - 5 * p - om.fee(5, p, 0.5))
    plenty = [at(b, 10, 0.95, 500)]             # more than $10 traded: the full 10 / p contracts
    for won in (True, False):
        out = dt.check(bet(won=won), plenty)
        assert out["pnl_capped"] == pytest.approx(out["pnl_backtest"])


def test_pnl_capped_uses_the_capped_price(dt, study):
    om = study.other_markets
    b = bet(ask=0.998)                          # p = 0.999, not 1.002
    out = dt.check(b, [at(b, 10, 0.999, 4)])
    assert out["pnl_capped"] == pytest.approx(4 - 4 * 0.999 - om.fee(4, 0.999, 1))
    assert out["pnl_backtest"] == pytest.approx(backtest(om, 0.998, True, 1))


def test_pnl_capped_is_zero_with_nothing_to_buy(dt):
    b = bet()
    for tape in ([], [at(b, 10, 0.97, 100)], [at(b, 300, 0.95, 100)], [at(b, 10, 0.95, 100, side="no")]):
        assert dt.check(b, tape)["pnl_capped"] == 0.0
        assert dt.check(bet(won=False), tape)["pnl_capped"] == 0.0


# ------------------------------------------------------------------ summarise

BEFORE = SPLIT - 10 * 86400                     # Aug 22


def checked(close, key=TEMP_10, any_win=False, soon=0.0, win=0.0, pnl_backtest=0.44, pnl_capped=0.0):
    """check()'s dict for a bet, by hand: soon and win given in dollars at 95c."""
    return dict(bet(key=key, close=close, cp=close - 600), soon=(soon / 0.95, soon), win=(win / 0.95, win),
                any_win=any_win, first=None, full10=win >= 10, pnl_backtest=pnl_backtest, pnl_capped=pnl_capped)


def summary_rows():
    return [checked(BEFORE, any_win=True, soon=12, win=30, pnl_backtest=0.44, pnl_capped=0.44),     # full
            checked(BEFORE + 3600, any_win=True, soon=2, win=12, pnl_backtest=-10.04, pnl_capped=-10.04),   # full, lost
            checked(BEFORE + 7200, any_win=True, soon=0, win=4, pnl_backtest=0.44, pnl_capped=0.18),
            checked(SPLIT - 1, any_win=False, pnl_backtest=0.44, pnl_capped=0.0),                   # the last before
            checked(SPLIT, any_win=False, soon=0, win=9.99, pnl_backtest=0.44, pnl_capped=0.40),   # the first after
            checked(SPLIT + 86400, key=ECON_1, any_win=True, soon=20, win=40, pnl_backtest=0.2, pnl_capped=0.2),
            checked(SPLIT + 2 * 86400, key=ECON_1, any_win=True, soon=5, win=10, pnl_backtest=0.3, pnl_capped=0.3)]


def test_summarise_splits_the_halves_at_split_by_close(dt):
    s = dt.summarise(summary_rows())
    assert set(s) == {(TEMP_10, "before"), (TEMP_10, "after"), (TEMP_10, "all"), (ECON_1, "after"), (ECON_1, "all")}
    assert s[(TEMP_10, "before")]["bets"] == 4
    assert s[(TEMP_10, "after")]["bets"] == 1
    assert s[(TEMP_10, "all")]["bets"] == 5
    assert s[(ECON_1, "after")]["bets"] == s[(ECON_1, "all")]["bets"] == 2


def test_summarise_gives_shares_as_fractions(dt):
    s = dt.summarise(summary_rows())
    before = s[(TEMP_10, "before")]
    assert before["any_win"] == pytest.approx(0.75)
    assert before["soon10"] == pytest.approx(0.25)
    assert before["full10"] == pytest.approx(0.5)
    after = s[(TEMP_10, "after")]
    assert (after["any_win"], after["soon10"], after["full10"]) == (0, 0, 0)
    every = s[(TEMP_10, "all")]
    assert every["any_win"] == pytest.approx(0.6) and every["full10"] == pytest.approx(0.4)
    econ = s[(ECON_1, "all")]
    assert econ["full10"] == 1.0 and econ["soon10"] == pytest.approx(0.5)      # exactly $10 is full


def test_summarise_takes_the_median_of_the_win_dollars(dt):
    s = dt.summarise(summary_rows())
    assert s[(TEMP_10, "before")]["median_win_dollars"] == pytest.approx(8.0)    # 0, 4, 12, 30
    assert s[(TEMP_10, "all")]["median_win_dollars"] == pytest.approx(9.99)      # 0, 4, 9.99, 12, 30
    assert s[(TEMP_10, "after")]["median_win_dollars"] == pytest.approx(9.99)
    assert s[(ECON_1, "all")]["median_win_dollars"] == pytest.approx(25.0)


def test_summarise_means_are_per_bet(dt):
    s = dt.summarise(summary_rows())
    before = s[(TEMP_10, "before")]
    assert before["pnl_backtest"] == pytest.approx((0.44 - 10.04 + 0.44 + 0.44) / 4)
    assert before["pnl_capped"] == pytest.approx((0.44 - 10.04 + 0.18 + 0.0) / 4)
    assert before["capped_total"] == pytest.approx(0.44 - 10.04 + 0.18)
    every = s[(TEMP_10, "all")]
    assert every["pnl_backtest"] == pytest.approx((0.44 * 4 - 10.04) / 5)
    assert every["pnl_capped"] == pytest.approx((0.44 - 10.04 + 0.18 + 0.40) / 5)
    assert every["capped_total"] == pytest.approx(0.44 - 10.04 + 0.18 + 0.40)
    assert s[(ECON_1, "after")]["capped_total"] == pytest.approx(0.5)


def test_pnl_full10_only_is_over_the_full_bets(dt):
    s = dt.summarise(summary_rows())
    assert s[(TEMP_10, "before")]["pnl_full10_only"] == pytest.approx((0.44 - 10.04) / 2)
    assert s[(TEMP_10, "all")]["pnl_full10_only"] == pytest.approx((0.44 - 10.04) / 2)
    assert s[(TEMP_10, "after")]["pnl_full10_only"] is None          # its one bet traded $9.99
    assert s[(ECON_1, "all")]["pnl_full10_only"] == pytest.approx(0.25)


def test_summarise_of_nothing(dt):
    assert dt.summarise([]) == {}


def test_summarise_keeps_keys_apart(dt):
    rows = [checked(BEFORE, key=k, win=w, pnl_backtest=x, pnl_capped=x)
            for k, w, x in ((TEMP_10, 20, 1.0), (TEMP_30, 0, -2.0), (ECON_2, 15, 3.0))]
    s = dt.summarise(rows)
    assert {k for k, _ in s} == {TEMP_10, TEMP_30, ECON_2}
    assert [s[(k, "all")]["pnl_backtest"] for k in (TEMP_10, TEMP_30, ECON_2)] == [1.0, -2.0, 3.0]
    assert s[(TEMP_30, "before")]["full10"] == 0 and s[(ECON_2, "before")]["full10"] == 1


# ------------------------------------------------------------------ fetch (fake HTTP)

NEW = "KXTEMPNYCH-26SEP2014-T71.99"            # closes Sep 20, after the cutoff
OLD = "KXAAAGASD-26AUG02-3.45"                 # closes Aug 2, before it
OLD_CLOSE = ts("2026-08-02T04:00:00Z")


def tape_bet(ticker=NEW, close=CLOSE, unit="min", key=TEMP_10, k=600):
    return bet(ticker=ticker, series=ticker.split("-")[0], close=close, cp=close - k, unit=unit, key=key)


NEW_BET = tape_bet()
OLD_BET = tape_bet(OLD, OLD_CLOSE, "hour", ECON_1, 3600)


def stamp(t):
    """A unix time as Kalshi writes created_time: ISO, to the millisecond, in UTC."""
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def trade(t, yes_price, count, taker):
    """A trade as Kalshi's trades endpoints give it."""
    return {"trade_id": f"t-{t}", "created_time": stamp(t), "yes_price_dollars": f"{yes_price:.4f}",
            "no_price_dollars": f"{1 - yes_price:.4f}", "count_fp": f"{count:.2f}", "taker_side": taker}


# (seconds before the close, YES price, contracts, taker side); inside both units' spans, one after the close
LIVE = [(587.875, 0.96, 12.5, "yes"), (1740, 0.94, 3.0, "no"), (-30, 0.99, 40.0, "yes"), (587.25, 0.95, 1.0, "yes"),
        (900, 0.03, 7.25, "no")]
HIST = [(2000, 0.02, 100.0, "no"), (1210.25, 0.03, 5.5, "no"), (300, 0.97, 2.0, "yes")]


def trades(close, shape):
    return [trade(close - s, p, c, side) for s, p, c, side in shape]


NEW_LIVE, NEW_HIST = trades(CLOSE, LIVE), trades(CLOSE, HIST)
OLD_LIVE, OLD_HIST = trades(OLD_CLOSE, LIVE), trades(OLD_CLOSE, HIST)


class Kalshi:
    """Stands in for dt.get: the cutoff, and each ticker's trades on the live endpoint (/markets/trades) and the
    historical one (/historical/trades). Like Kalshi it keeps to [min_ts, max_ts] and serves newest first, `page`
    at a time with a cursor. A ticker mapped to None answers None, as get does for a 404."""

    def __init__(self, live=None, hist=None, cutoff=CUTOFF_ISO, page=2):
        self.stores = {"live": live or {}, "hist": hist or {}}
        self.cutoff, self.page, self.calls = cutoff, page, []

    def __call__(self, url, params=None, **kwargs):
        params = dict(params or {})
        self.calls.append((url, params))
        assert len(self.calls) < 300, "fetch kept asking"
        if url.rstrip("/").endswith("/historical/cutoff"):
            return {"market_settled_ts": self.cutoff}
        if url.endswith("/historical/trades"):
            store = "hist"
        elif url.endswith("/markets/trades"):
            store = "live"
        else:
            raise AssertionError(f"unexpected request: {url}")
        trades = self.stores[store].get(params.get("ticker"), [])
        if trades is None:
            return None
        lo, hi = params.get("min_ts", float("-inf")), params.get("max_ts", float("inf"))
        trades = sorted((x for x in trades if lo <= ts(x["created_time"]) <= hi), key=lambda x: x["created_time"],
                        reverse=True)
        start = int(params.get("cursor") or 0)
        end = start + self.page
        return {"trades": trades[start:end], "cursor": str(end) if end < len(trades) else ""}

    def asked(self, ticker):
        """(endpoint, params) of each trades request for the ticker, in order."""
        return [("hist" if u.endswith("/historical/trades") else "live", p) for u, p in self.calls
                if p.get("ticker") == ticker and u.endswith("/trades")]

    def cutoff_asked(self):
        return any(u.rstrip("/").endswith("/historical/cutoff") for u, _ in self.calls)


def lines(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def by_ticker(path):
    return {d["t"]: d["tr"] for d in lines(path)}


def run_fetch(dt, monkeypatch, tmp_path, kalshi, bets, name="tape.jsonl"):
    monkeypatch.setattr(dt, "get", kalshi)
    monkeypatch.setattr(dt, "tape_bets", lambda: list(bets))
    out = tmp_path / name
    dt.fetch(str(out))
    return out


def rows_of(trades):
    return sorted([ts(x["created_time"]), float(x["yes_price_dollars"]), float(x["count_fp"]), x["taker_side"]]
                  for x in trades)


def same_rows(got, trades):
    want = rows_of(trades)
    assert len(got) == len(want)
    for g, w in zip(sorted(got), want):
        assert g[0] == pytest.approx(w[0], abs=1e-3) and g[1:] == w[1:]


def test_fetch_defaults_to_the_tape_file(dt):
    assert inspect.signature(dt.fetch).parameters["path"].default == dt.TAPE
    assert callable(dt.get)


def test_fetch_asks_live_first_for_a_market_closing_after_the_cutoff(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: NEW_LIVE}, hist={NEW: NEW_HIST})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    assert k.cutoff_asked()
    assert {e for e, _ in k.asked(NEW)} == {"live"}             # it had trades: the historical store isn't asked
    same_rows(by_ticker(out)[NEW], NEW_LIVE)


def test_fetch_asks_the_historical_store_first_before_the_cutoff(dt, monkeypatch, tmp_path):
    k = Kalshi(live={OLD: OLD_LIVE}, hist={OLD: OLD_HIST})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [OLD_BET])
    assert {e for e, _ in k.asked(OLD)} == {"hist"}
    same_rows(by_ticker(out)[OLD], OLD_HIST)


def test_the_cutoff_decides_which_endpoint_comes_first(dt, monkeypatch, tmp_path):
    """The same market, with the cutoff moved past its close: now it's the historical store's."""
    k = Kalshi(live={NEW: NEW_LIVE}, hist={NEW: NEW_HIST}, cutoff="2026-10-01T00:00:00Z")
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    assert {e for e, _ in k.asked(NEW)} == {"hist"}
    same_rows(by_ticker(out)[NEW], NEW_HIST)


@pytest.mark.parametrize("empty", [[], None])
def test_fetch_falls_back_to_the_historical_store_when_live_has_nothing(dt, monkeypatch, tmp_path, empty):
    k = Kalshi(live={NEW: empty}, hist={NEW: NEW_HIST})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    asked = [e for e, _ in k.asked(NEW)]
    assert asked[0] == "live" and asked[-1] == "hist" and set(asked) == {"live", "hist"}
    same_rows(by_ticker(out)[NEW], NEW_HIST)


@pytest.mark.parametrize("empty", [[], None])
def test_fetch_falls_back_to_live_when_the_historical_store_has_nothing(dt, monkeypatch, tmp_path, empty):
    k = Kalshi(live={OLD: OLD_LIVE}, hist={OLD: empty})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [OLD_BET])
    asked = [e for e, _ in k.asked(OLD)]
    assert asked[0] == "hist" and asked[-1] == "live" and set(asked) == {"live", "hist"}
    same_rows(by_ticker(out)[OLD], OLD_LIVE)


def test_a_market_with_no_trades_anywhere_still_gets_a_line(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: []}, hist={NEW: None})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    assert {e for e, _ in k.asked(NEW)} == {"live", "hist"}
    assert lines(out) == [{"t": NEW, "tr": []}]


def test_fetch_asks_for_the_span_before_the_close_to_a_minute_after(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: [], OLD: OLD_LIVE}, hist={NEW: NEW_HIST, OLD: []})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET, OLD_BET])
    for ticker, close, span in ((NEW, CLOSE, 35 * 60), (OLD, OLD_CLOSE, 150 * 60)):
        asked = k.asked(ticker)
        assert len(asked) >= 2                   # both endpoints, each with the same window
        for _, p in asked:
            assert p["ticker"] == ticker
            assert p["min_ts"] == close - span and p["max_ts"] == close + 60
    got = by_ticker(out)
    same_rows(got[NEW], NEW_HIST)
    same_rows(got[OLD], OLD_LIVE)


def test_fetch_follows_the_cursor(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: NEW_LIVE}, page=2)     # 5 trades: pages of 2, 2 and 1
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    assert [p.get("cursor") or None for _, p in k.asked(NEW)] == [None, "2", "4"]
    same_rows(by_ticker(out)[NEW], NEW_LIVE)


def test_fetch_follows_the_cursor_on_the_fallback_too(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: []}, hist={NEW: NEW_LIVE + NEW_HIST}, page=3)
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    assert [p.get("cursor") or None for e, p in k.asked(NEW) if e == "hist"] == [None, "3", "6"]
    same_rows(by_ticker(out)[NEW], NEW_LIVE + NEW_HIST)


def test_tape_rows_are_parsed_and_sorted_by_time(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: NEW_LIVE}, page=10)
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    (line,) = lines(out)
    assert set(line) == {"t", "tr"} and line["t"] == NEW
    tr = line["tr"]
    assert [x[0] for x in tr] == sorted(x[0] for x in tr)
    assert tr[0] == [pytest.approx(CLOSE - 1740, abs=1e-3), 0.94, 3.0, "no"]
    assert tr[1] == [pytest.approx(CLOSE - 900, abs=1e-3), 0.03, 7.25, "no"]
    assert tr[2] == [pytest.approx(CLOSE - 587.875, abs=1e-3), 0.96, 12.5, "yes"]
    assert tr[3] == [pytest.approx(CLOSE - 587.25, abs=1e-3), 0.95, 1.0, "yes"]
    assert tr[4] == [pytest.approx(CLOSE + 30, abs=1e-3), 0.99, 40.0, "yes"]
    assert all(isinstance(x[1], float) and isinstance(x[2], float) for x in tr)


def test_one_line_per_ticker_even_with_two_bets(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: NEW_LIVE})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET, tape_bet(key=TEMP_30, k=1800)])
    assert [d["t"] for d in lines(out)] == [NEW]
    assert [p.get("cursor") or None for _, p in k.asked(NEW)] == [None, "2", "4"]


def test_fetch_resumes_skipping_tickers_already_in_the_file(dt, monkeypatch, tmp_path):
    out = tmp_path / "tape.jsonl"
    kept = '{"t": "%s", "tr": [[1785000000.0, 0.97, 2.0, "yes"]]}\n' % OLD
    out.write_text(kept)
    k = Kalshi(live={NEW: NEW_LIVE, OLD: OLD_LIVE}, hist={OLD: OLD_HIST})
    run_fetch(dt, monkeypatch, tmp_path, k, [OLD_BET, NEW_BET])
    assert k.asked(OLD) == []
    assert out.read_text().startswith(kept)
    assert [d["t"] for d in lines(out)] == [OLD, NEW]
    same_rows(by_ticker(out)[NEW], NEW_LIVE)
    before = out.read_text()
    again = Kalshi(live={NEW: NEW_LIVE, OLD: OLD_LIVE}, hist={OLD: OLD_HIST})
    run_fetch(dt, monkeypatch, tmp_path, again, [OLD_BET, NEW_BET])
    assert again.asked(OLD) == again.asked(NEW) == []
    assert out.read_text() == before


def test_a_ticker_with_an_empty_line_is_not_asked_again(dt, monkeypatch, tmp_path):
    k = Kalshi(live={NEW: []}, hist={NEW: []})
    out = run_fetch(dt, monkeypatch, tmp_path, k, [NEW_BET])
    again = Kalshi(live={NEW: NEW_LIVE})
    run_fetch(dt, monkeypatch, tmp_path, again, [NEW_BET])
    assert again.asked(NEW) == []
    assert lines(out) == [{"t": NEW, "tr": []}]


def test_fetch_writes_every_ticker(dt, monkeypatch, tmp_path):
    others = [tape_bet(f"KXTEMPCHIH-26SEP{d:02d}14-T80.99", CLOSE - (20 - d) * 86400) for d in range(10, 15)]
    live = {b["ticker"]: trades(b["close"], LIVE[: i + 1]) for i, b in enumerate(others)}
    k = Kalshi(live=live, hist={OLD: OLD_HIST})
    out = run_fetch(dt, monkeypatch, tmp_path, k, others + [OLD_BET])
    got = by_ticker(out)
    assert set(got) == set(live) | {OLD}
    for t, want in live.items():
        same_rows(got[t], want)
    same_rows(got[OLD], OLD_HIST)


# ------------------------------------------------------------------ main


def test_main_fetch_runs_fetch(dt, monkeypatch):
    calls = []
    monkeypatch.setattr(dt, "fetch", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(dt, "get", Kalshi())
    monkeypatch.setattr(sys, "argv", ["depth_tape.py", "fetch"])
    dt.main()
    assert len(calls) == 1 and calls[0] in (((), {}), ((dt.TAPE,), {}), ((), {"path": dt.TAPE}))


def test_main_reports_the_summary_and_the_bets_without_a_tape_line(dt, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    a, b = NEW, "KXTEMPMIAH-26SEP2014-T88.99"
    with_line = [tape_bet(a), tape_bet(a, key=TEMP_30, k=1800), tape_bet(b),
                 tape_bet(OLD, OLD_CLOSE, "hour", ECON_1, 3600)]
    without = [tape_bet(f"KXTEMPAUSH-26SEP{d}14-T90.99", CLOSE - 86400 * i, key=key, k=k)
               for i, d in enumerate((11, 12, 13)) for key, k in ((TEMP_10, 600), (TEMP_30, 1800))]
    without.append(tape_bet("KXSOFRD-26AUG01-4.30", OLD_CLOSE - 86400, "hour", ECON_2, 7200))
    assert len(without) == 7 and len({x["ticker"] for x in without}) == 4
    cp = CLOSE - 600
    tape = {a: [[cp + 5, 0.95, 20.0, "yes"], [cp + 100, 0.99, 3.0, "yes"]],
            b: [],
            OLD: [[OLD_CLOSE - 3600 + 30, 0.97, 50.0, "yes"]]}
    with open(dt.TAPE, "w") as fh:
        for t, tr in tape.items():
            fh.write(json.dumps({"t": t, "tr": tr}) + "\n")
    monkeypatch.setattr(dt, "tape_bets", lambda: with_line[:2] + without[:3] + with_line[2:] + without[3:])

    def refuse(*args, **kwargs):
        raise AssertionError("the report made a request")
    monkeypatch.setattr(dt, "get", refuse)
    monkeypatch.setattr(dt, "fetch", refuse)
    given = []
    real = dt.summarise
    monkeypatch.setattr(dt, "summarise", lambda checked: given.append(list(checked)) or real(given[-1]))
    monkeypatch.setattr(sys, "argv", ["depth_tape.py"])
    dt.main()
    out = capsys.readouterr().out
    assert given
    order = lambda c: (c["ticker"], c["cp"])
    assert sorted(given[0], key=order) == sorted((dt.check(x, tape[x["ticker"]]) for x in with_line), key=order)
    assert any(re.search(r"\b7\b", line) and "tape" in line.lower() for line in out.splitlines()), out
    assert "Climate" in out and "Economics" in out


def test_main_counts_every_bet_with_a_line_as_checked(dt, monkeypatch, tmp_path):
    """Every bet has its line (one with no trades): none is left out."""
    monkeypatch.chdir(tmp_path)
    with open(dt.TAPE, "w") as fh:
        fh.write(json.dumps({"t": NEW, "tr": []}) + "\n")
    monkeypatch.setattr(dt, "tape_bets", lambda: [NEW_BET])
    monkeypatch.setattr(sys, "argv", ["depth_tape.py"])
    given = []
    real = dt.summarise
    monkeypatch.setattr(dt, "summarise", lambda checked: given.append(list(checked)) or real(given[-1]))
    dt.main()
    assert given and given[0] == [dt.check(NEW_BET, [])]
