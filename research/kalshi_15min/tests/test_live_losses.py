"""live_losses.py: how the live bot's losses happened, and the skip rule they suggested (skip a 90-92c favourite whose
spread is over 0.2c), tested on the backtest. Written before the script, so these
tests are its contract.

What is pinned:
  read_bets      the settled bets of a temp ledger made by bot.connect (the bot's own tables), oldest placed first, each
                 the bets row plus ask (the decision's fav_price, else the fill price), spread (the decision's yes_ask -
                 yes_bid to 4 places, else None) and crypto (False only for the five metals and two energy series).
                 Open bets are left out, and a missing file gives []. The file is opened read-only: a mode=ro URI, and a
                 write through it is refused. It is left exactly as it was (bytes, modified time, folder listing), with no
                 handle held.
  band_of, WIDE  each edge (0.90, 0.92, 0.94, 0.999, 0.899 and a hair either side). "Wide" is 90-92c with a spread over
                 0.2c by more than float noise, checked through live_summary's wide/rest split.
  fav_mids, first_flip, poisson_tail
                 the YES mid, the NO side's 1 - mid, the last price when a quote is missing, carry-forward and leading
                 None. Minute 8 is the entry and never a flip. The tail is checked against a direct sum.
  live_summary   twelve hand-made bets over three ET days: totals, every band in BANDS order (an empty one with implied
                 None), wide/rest, watch (null without a share or without a 90-92c bet), flips/flipsOf, clusters (metals
                 and energy don't count) and days by the ET date of close_ts (a 23:30 ET window stays on its own day).
                 Money is rounded to 2 places and p to 3.
  rule_test      a synthetic d shaped like common.load()'s: seven favourites a window, their sides, asks and spreads set
                 on the masks' edges, plus markets the live rule must refuse (89c, a 2c spread, a late favourite, two Fed
                 afternoons). Every row and family S is checked against common.summary on masks built here by hand. Also
                 the holdout's choice (lowest mu, ties to the first in family order), holds, sizing (edge_map.replay),
                 the periods and the backtest's loss share per band.
  fetch_paths    a fake get: only uncached windows are fetched, 20 tickers a call, with the exact params, k from
                 end_period_ts, close then previous. A failed reply is tried again next run, and rows are appended to the
                 CSV cache.
  main           with the ledger, the candles, C.load and get stubbed, and once end to end on a temp ledger: it writes
                 live_losses.json with asOf, live and rule, as strict JSON (no NaN).

Readings of the spec (where it leaves a choice, these tests pin this one):
  1. S is common.summary()'s dict as it returns it: pnl in $ (summary rounds it to 2 places), and perBet, mu, lo and hi
     in cents per $10, unrounded (they are rates, not money). lost (the share lost) and implied (the mean of 1 - the
     recorded ask, no slip) are added, also unrounded. With no bets, every field but bets is None, pnl included (the spec
     says "the other fields are None", not summary's 0.0).
  2. live.from / live.to are numbers: the first bet's window_open and the last bet's close_ts, in the order read_bets
     gives (oldest placed first). With no bets they are None, the counts are 0 and the money 0.0. Every band is still
     there with 0 bets, watch is None, every flip minute is 0, and days is [].
  3. flips counts lost bets only. A lost bet with no mids (its ticker absent from fav_mids) counts in neither flipsOf nor
     any minute. One with mids whose favourite never went under 50c in minutes 9-15 counts in flipsOf only. A mid of
     exactly 50c is not under 50c.
  4. A band's "backtest" is backtest_loss.get(key). It is there even for a band with no live bets (the dashboard shows
     "—" itself), and None only when backtest_loss lacks the key.
  5. A bet whose ask is outside every band (an 89c fav_price) counts in the totals, in days and in rest, and in no band.
  6. watch: p = poisson_tail(lost, expected), with expected already rounded to 2 places. The numbers here make the
     unrounded reading give the same p.
  7. Period labels use UTC dates, not ET. The spec says "(ET)", but its own example ("Jul 18 – Oct 8" for post) only
     comes out in UTC: the first post window opens Jul 18 00:00 UTC, which is Jul 17 8 pm ET. The periods' bounds are UTC
     midnights (common.PERIODS), and the old Research tab formatted days in UTC. Each label runs from the period's first window
     open to the last second of its last window (open + 899, as the dashboard's day(to - 1) does). The windows are all of
     d's markets in that period, not just the bets.
  8. rule.from / rule.to are whole seconds: d's first open_ts, and its last open_ts + 900.
  9. The holdout never chooses a family row with no bets on chosenOn. holds is False when a scored hi is None (too few
     bets for a range).
 10. read_bets: a decision row whose fav_price is NULL falls back to price too. One whose yes_bid or yes_ask is NULL (as
     the bot's reconcile writes them) gives spread None. Each dict is exactly the bets columns plus ask, spread and
     crypto. The connection is closed before it returns.
 11. fetch_paths: start_ts and end_ts are ints. window_open is a REAL in the ledger, and Kalshi takes whole seconds. The
     reply has the batch endpoint's shape, {"markets": [{"market_ticker", "candlesticks"}]}, as fetch_minutes.py reads
     it. A block value that is null falls back like a missing one. Every row it returns, cached or new, is {"ticker",
     "k": int, "b"/"a"/"p": float or None}, and the CSV writes None as "".
 12. fav_mids ignores rows with k outside 1-15, leaves out tickers that aren't in sides, and doesn't need its rows in
     minute order.
 13. main reads module constants LEDGER (bot/state/live-prod.db), CACHE (live_losses_paths.csv) and OUT
     (live_losses.json). Each is an absolute path next to the script, so the script works from any folder. The sides it
     gives fav_mids are {ticker: side} of the bets.

    python -m pytest research/kalshi_15min/tests/test_live_losses.py -q
"""

from __future__ import annotations

import ast
import csv
import importlib
import inspect
import json
import math
import os
import socket
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from conftest import RESEARCH

REPO = RESEARCH.parent.parent
LAB = RESEARCH / "lab"
UTC = timezone.utc
ET = ZoneInfo("America/New_York")
NOT_CRYPTO = ("KXCOPPER15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXWTI15M", "KXNATGAS15M")
CRYPTO = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXHYPE15M", "KXBNB15M")
BET_COLUMNS = ("id", "ticker", "series", "window_open", "close_ts", "side", "price", "contracts", "cost", "fee",
               "placed_ts", "order_id", "client_order_id", "status", "result", "payout", "pnl", "settled_ts")
S_KEYS = {"bets", "perBet", "mu", "lo", "hi", "pnl", "lost", "implied"}
TALLY = {"bets", "lost", "pnl", "staked"}
FAMILY_ORDER = [(hi, s) for hi in (0.91, 0.92, 0.93, 0.94) for s in (None, 0.001, 0.002, 0.004, 0.009)]


def et(s):
    return datetime.fromisoformat(s).replace(tzinfo=ET).timestamp()


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp()


def strict(text):
    """json.loads that refuses NaN and Infinity: json.dump writes them, but JSON (and the dashboard) doesn't take them."""
    def bad(x):
        raise ValueError(f"not JSON: {x}")
    return json.loads(text, parse_constant=bad)


def roundtrip(x):
    return json.loads(json.dumps(x, allow_nan=False))


# ------------------------------------------------------------------ fixtures and guards
@pytest.fixture(scope="module")
def ll(study):
    """live_losses, imported once the synthetic study is the working directory (as test_price_floor does). While the
    script doesn't exist, this fails and so does every test here."""
    return importlib.import_module("live_losses")


@pytest.fixture(scope="module")
def lab(ll):
    """The strategy lab's common and edge_map, the modules live_losses reuses, imported by name from lab/."""
    if str(LAB) not in sys.path:
        sys.path.insert(0, str(LAB))
    return SimpleNamespace(C=importlib.import_module("common"), E=importlib.import_module("edge_map"))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test here may reach Kalshi: a fake get that misses a request fails the test instead of going out."""
    def refuse(*args, **kwargs):
        raise OSError("the live_losses tests never use the network")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def temp_ledgers_only(monkeypatch, tmp_path_factory):
    """sqlite3.connect refusing any database outside pytest's temp folders, so no default can reach a real ledger."""
    real = sqlite3.connect
    base = str(Path(tmp_path_factory.getbasetemp()).resolve()).replace("\\", "/").lower()

    def connect(database, *args, **kwargs):
        name = os.fspath(database)
        if name not in ("", ":memory:") and not name.startswith("file::memory:"):
            plain = unquote(name.split("?", 1)[0])
            plain = plain[5:].lstrip("/") if plain.startswith("file:") else os.path.abspath(plain)
            if base not in plain.replace("\\", "/").lower():
                raise AssertionError(f"opened a database outside the tests' temp folders: {name}")
        return real(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", connect)


def test_the_bands_and_the_spread_line(ll):
    assert ll.BANDS == (("90-92", "90–92¢", 0.90, 0.92), ("92-94", "92–94¢", 0.92, 0.94),
                        ("94+", "94¢ and up", 0.94, 0.999))
    assert ll.WIDE == 0.002


def test_the_files_sit_beside_the_script_whatever_the_working_folder(ll):
    assert Path(ll.LEDGER).resolve() == (REPO / "bot" / "state" / "live-prod.db").resolve()
    assert Path(ll.CACHE).resolve() == (RESEARCH / "live_losses_paths.csv").resolve()
    assert Path(ll.OUT).resolve() == (RESEARCH / "live_losses.json").resolve()


def test_poisson_tail_uses_the_math_module_only(ll):
    tree = ast.parse(inspect.getsource(ll))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [x for x in names if x.split(".")[0] == "scipy"], "no scipy"


# ------------------------------------------------------------------ read_bets: a ledger written the way the bot writes it
W_A, W_B = et("2026-09-28T10:00"), et("2026-09-28T10:15")


def ledger_bet(ticker, status, placed, price, window=W_A, side="yes", contracts=10.0):
    cost = round(contracts * price, 4)
    settled = status in ("won", "lost")
    payout = (contracts if status == "won" else 0.0) if settled else None
    other = "no" if side == "yes" else "yes"
    return {"ticker": ticker, "series": ticker.split("-")[0], "window_open": window, "close_ts": window + 900,
            "side": side, "price": price, "contracts": contracts, "cost": cost, "fee": 0.06, "placed_ts": placed,
            "order_id": f"order-{ticker}", "client_order_id": f"cid-{ticker}", "status": status,
            "result": (side if status == "won" else other) if settled else None, "payout": payout,
            "pnl": round(payout - cost - 0.06, 4) if settled else None, "settled_ts": window + 905 if settled else None}


def decision(ticker, yes_bid, yes_ask, fav_price, side="yes", action="bet"):
    return {"ts": W_A + 480, "ticker": ticker, "series": ticker.split("-")[0], "yes_bid": yes_bid, "yes_ask": yes_ask,
            "fav_side": side, "fav_price": fav_price, "action": action, "reason": f"{action} {ticker}"}


def write_ledger(path, bets=(), decisions=()):
    """A ledger made by bot.connect (the live bot's own tables) holding these rows, committed and closed."""
    from kalshi_bot import bot
    db = bot.connect(str(path))
    try:
        for table, rows in (("bets", bets), ("decisions", decisions)):
            for r in rows:
                cols = list(r)
                db.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                           [r[c] for c in cols])
        db.commit()
    finally:
        db.close()
    return Path(path)


# Inserted in this order (ids 1-6), placed in another: read_bets sorts by placed_ts, not by id.
LEDGER_BETS = [
    ledger_bet("KXBTC15M-26SEP281015-15", "won", W_A + 483, 0.905),                 # a decision with its book
    ledger_bet("KXGOLD15M-26SEP281015-4000", "lost", W_A + 481, 0.96, side="no"),    # a NO favourite; a metal
    ledger_bet("KXETH15M-26SEP281015-15", "open", W_A + 482, 0.93),                  # still open: left out
    ledger_bet("KXWTI15M-26SEP281015-70", "won", W_A + 482.5, 0.93),                 # no decision row at all
    ledger_bet("KXSOL15M-26SEP281030-30", "lost", W_B + 481, 0.92, window=W_B),      # a decision with no book
    ledger_bet("KXHYPE15M-26SEP281030-30", "won", W_B + 484, 0.95, window=W_B),      # a decision with no price
]
LEDGER_DECISIONS = [
    decision("KXBTC15M-26SEP281015-15", 0.911, 0.913, 0.913),            # the ask it saw, not the 90.5c fill
    decision("KXGOLD15M-26SEP281015-4000", 0.04, 0.05, 0.96, side="no"),
    decision("KXETH15M-26SEP281015-15", 0.92, 0.93, 0.93),
    decision("KXSOL15M-26SEP281030-30", None, None, 0.925),              # as the bot's reconcile writes one
    decision("KXHYPE15M-26SEP281030-30", 0.95, 0.952, None),
    decision("KXXRP15M-26SEP281015-15", 0.50, 0.52, 0.52, action="skip"),   # a market it didn't buy
]
# ticker -> (id, ask, spread, crypto), oldest placed first
LEDGER_WANT = {
    "KXGOLD15M-26SEP281015-4000": (2, 0.96, 0.01, False),
    "KXWTI15M-26SEP281015-70": (4, 0.93, None, False),
    "KXBTC15M-26SEP281015-15": (1, 0.913, 0.002, True),
    "KXSOL15M-26SEP281030-30": (5, 0.925, None, True),
    "KXHYPE15M-26SEP281030-30": (6, 0.95, 0.002, True),
}


@pytest.fixture
def ledger(tmp_path):
    return write_ledger(tmp_path / "live-test.db", LEDGER_BETS, LEDGER_DECISIONS)


def test_read_bets_gives_the_settled_bets_oldest_first_with_ask_spread_and_crypto(ll, ledger):
    bets = ll.read_bets(ledger)
    assert [b["ticker"] for b in bets] == list(LEDGER_WANT), "settled only, by placed_ts"
    rows = {r["ticker"]: r for r in LEDGER_BETS}
    for b in bets:
        i, ask, spread, crypto = LEDGER_WANT[b["ticker"]]
        assert set(b) == set(BET_COLUMNS) | {"ask", "spread", "crypto"}, "the bets columns plus three"
        assert {k: b[k] for k in rows[b["ticker"]]} == rows[b["ticker"]] and b["id"] == i
        assert b["ask"] == ask and b["crypto"] is crypto, b["ticker"]
        assert b["spread"] is None if spread is None else b["spread"] == pytest.approx(spread, abs=1e-12)
    assert all(b["spread"] is None or b["spread"] == round(b["spread"], 4) for b in bets), "to 4 places"


def test_read_bets_falls_back_to_the_fill_price_without_a_decision(ll, ledger):
    bets = {b["ticker"]: b for b in ll.read_bets(str(ledger))}
    wti = bets["KXWTI15M-26SEP281015-70"]
    assert (wti["ask"], wti["spread"]) == (0.93, None), "no decision row: price, and no spread"
    assert bets["KXHYPE15M-26SEP281030-30"]["ask"] == 0.95, "a decision with no fav_price: price too"
    assert bets["KXSOL15M-26SEP281030-30"]["spread"] is None, "a decision with no book: no spread"
    assert "KXETH15M-26SEP281015-15" not in bets, "an open bet is left out"


def test_read_bets_marks_only_metals_and_energy_as_not_crypto(ll, tmp_path):
    rows = [ledger_bet(f"{s}-26SEP281015-1", "won", W_A + 480 + i, 0.95) for i, s in enumerate(NOT_CRYPTO + CRYPTO)]
    path = write_ledger(tmp_path / "series.db", rows)
    got = {b["series"]: b["crypto"] for b in ll.read_bets(path)}
    assert got == {**{s: False for s in NOT_CRYPTO}, **{s: True for s in CRYPTO}}


def test_read_bets_leaves_the_file_exactly_as_it_was(ll, ledger):
    folder = ledger.parent
    before = (ledger.read_bytes(), os.stat(ledger).st_mtime_ns, sorted(p.name for p in folder.iterdir()))
    ll.read_bets(ledger)
    ll.read_bets(str(ledger))
    after = (ledger.read_bytes(), os.stat(ledger).st_mtime_ns, sorted(p.name for p in folder.iterdir()))
    assert after[0] == before[0], "byte for byte"
    assert after[1] == before[1], "its modified time too"
    assert after[2] == before[2] == ["live-test.db"], "no -journal, -wal or -shm file left beside it"
    ledger.rename(folder / "moved.db")   # closed before it returns: on Windows an open handle would refuse this


def test_read_bets_opens_the_ledger_read_only(ll, ledger, monkeypatch):
    """Every connection to the file is a mode=ro URI, and a second connection opened the same way refuses a write."""
    guarded = sqlite3.connect
    opened, writable = [], []

    def spy(database, *args, **kwargs):
        con = guarded(database, *args, **kwargs)
        name = os.fspath(database)
        if name not in ("", ":memory:") and not name.startswith("file::memory:"):
            opened.append((name, kwargs.get("uri")))
            probe = guarded(database, *args, **kwargs)
            try:
                probe.execute("INSERT INTO meta VALUES ('probe', 'x')")
            except sqlite3.OperationalError:
                pass
            else:
                writable.append(name)
                probe.rollback()
            finally:
                probe.close()
        return con
    monkeypatch.setattr(sqlite3, "connect", spy)
    assert len(ll.read_bets(ledger)) == len(LEDGER_WANT)
    assert opened, "it opened the ledger"
    for name, uri in opened:
        assert uri is True and name.startswith("file:"), name
        assert "mode=ro" in name.split("?", 1)[1].split("&"), name
    assert not writable, "a write through its connection went through"


def test_read_bets_with_no_ledger_is_empty_and_creates_nothing(ll, tmp_path):
    missing = tmp_path / "nowhere" / "live-prod.db"
    assert ll.read_bets(missing) == [] and ll.read_bets(str(missing)) == []
    assert not missing.parent.exists()


# ------------------------------------------------------------------ band_of, first_flip, poisson_tail
@pytest.mark.parametrize("ask, band", [(0.90, "90-92"), (0.90 - 5e-10, "90-92"), (0.899, None), (0.91, "90-92"),
                                       (0.92, "90-92"), (0.92 + 5e-10, "90-92"), (0.9201, "92-94"), (0.94, "92-94"),
                                       (0.94 + 5e-10, "92-94"), (0.9401, "94+"), (0.999, "94+"),
                                       (0.999 + 5e-10, "94+"), (0.9995, None), (1.0, None), (0.50, None)])
def test_band_of_takes_the_first_band_covering_the_ask(ll, ask, band):
    assert ll.band_of(ask) == band


def flat(x=0.9, **at):
    """Fifteen minutes' favourite mids, x each minute but those given as m<k>=value."""
    out = [x] * 15
    for key, v in at.items():
        out[int(key[1:]) - 1] = v
    return out


@pytest.mark.parametrize("mids, minute", [
    (flat(m8=0.40), None),                                     # minute 8 is the entry, never a flip
    (flat(m8=0.40, m9=0.45), 9),                               # minute 9 is the first that counts
    (flat(), None),
    (flat(m10=0.5, m12=0.49, m13=0.2), 12),                    # exactly 50c is not under it
    (flat(m15=0.3), 15),                                       # the last minute counts
    (flat(m9=None, m10=0.3), 10),                              # a minute with no mid is passed over
    ([None] * 15, None),
], ids=["minute 8", "minute 9", "never", "50c", "minute 15", "a gap", "no mids"])
def test_first_flip_is_the_first_minute_from_9_under_50c(ll, mids, minute):
    assert ll.first_flip(mids) == minute


def direct_tail(k, mu, terms=150):
    """P(X >= k) summed term by term from k up (mu > 0)."""
    return math.fsum(math.exp(-mu + i * math.log(mu) - math.lgamma(i + 1)) for i in range(k, terms))


def test_poisson_tail(ll):
    assert ll.poisson_tail(0, 9.7) == pytest.approx(1.0, abs=1e-12) and ll.poisson_tail(0, 0.0) == pytest.approx(1.0)
    assert ll.poisson_tail(1, 0.0) == pytest.approx(0.0, abs=1e-12)
    assert round(ll.poisson_tail(16, 9.7), 3) == 0.039                          # the spec's worked example
    for mu in (0.3, 1.0, 2.7, 9.7):
        for k in range(13):
            assert ll.poisson_tail(k, mu) == pytest.approx(direct_tail(k, mu), abs=1e-12), (k, mu)


# ------------------------------------------------------------------ fav_mids
def test_fav_mids_gives_the_favourite_sides_mid_each_minute(ll):
    row = lambda t, k, b, a, p: {"ticker": t, "k": k, "b": b, "a": a, "p": p}  # noqa: E731
    rows = [
        row("Y", 1, None, None, None),        # nothing yet: a leading gap
        row("Y", 2, 0.60, 0.62, 0.55),        # both quotes: their mid, not the last price
        row("Y", 3, 0.70, None, 0.66),        # a quote missing: the last price
        row("Y", 5, None, 0.90, None),        # minute 4 has no row and 5 no mid: both carry minute 3 forward
        row("Y", 6, 0.80, 0.90, None),        # ... and minutes 7-15, with no rows, carry minute 6
        row("Y", 0, 0.01, 0.01, 0.01),        # outside 1-15: ignored
        row("Y", 16, 0.01, 0.01, 0.01),
        row("N", 2, 0.10, 0.12, None),        # a NO bet: 1 - the YES mid
        row("N", 4, None, None, 0.20),        # ... and 1 - the last price
        row("N", 9, 0.55, 0.57, 0.50),
        row("stranger", 3, 0.5, 0.6, 0.55),   # not one of the bets
    ]
    sides = {"Y": "yes", "N": "no", "quiet": "yes"}
    out = ll.fav_mids(list(reversed(rows)), sides)                # in no particular order
    assert set(out) == {"Y", "N"}, "tickers with no rows (or no side) are left out"
    assert len(out["Y"]) == len(out["N"]) == 15 and out["Y"][0] is None and out["N"][0] is None
    assert out["Y"][1:] == pytest.approx([0.61, 0.66, 0.66, 0.66] + [0.85] * 10)
    assert out["N"][1:] == pytest.approx([0.89, 0.89, 0.80, 0.80, 0.80, 0.80, 0.80] + [0.44] * 7)


# ------------------------------------------------------------------ live_summary: twelve bets over three ET days
W1, W2, W3, W4 = et("2026-09-28T10:00"), et("2026-09-28T23:30"), et("2026-09-29T15:00"), et("2026-09-30T09:30")
LIVE = [  # ticker, window, side, ask, spread, status, cost, pnl
    ("KXBTC15M-A", W1, "yes", 0.90, 0.002, "lost", 2.70, -2.7189),           # 90-92, a spread of exactly 0.2c
    ("KXETH15M-A", W1, "no", 0.91, 0.003, "lost", 2.73, -2.7489),            # 90-92, wide
    ("KXGOLD15M-A", W1, "yes", 0.95, None, "lost", 2.85, -2.8633),           # a metal
    ("KXSOL15M-A", W1, "yes", 0.96, 0.001, "won", 2.88, 0.1089),
    ("KXBTC15M-B", W2, "yes", 0.92, 0.0021, "lost", 5.52, -5.5531),          # 92c is 90-92; 0.21c is wide
    ("KXWTI15M-B", W2, "no", 0.97, 0.002, "lost", 5.82, -5.8375),            # energy
    ("KXETH15M-B", W2, "yes", 0.975, 0.001, "won", 5.85, 0.1395),
    ("KXXRP15M-C", W3, "yes", 0.905, 0.913 - 0.911, "won", 9.05, 0.8836),    # 0.2c and float noise: not wide
    ("KXDOGE15M-C", W3, "no", 0.96, 0.005, "won", 9.61, 0.3735),             # wide, but not 90-92
    ("KXBTC15M-D", W4, "yes", 0.999, 0.001, "won", 21.978, 0.0219),
    ("KXHYPE15M-D", W4, "yes", 0.89, 0.001, "won", 21.36, 2.5806),           # in no band
    ("KXBNB15M-D", W4, "yes", 0.91, None, "won", 21.84, 2.0748),             # no spread: never wide
]
MIDS = {
    "KXBTC15M-A": flat(m13=0.4, m14=0.3, m15=0.2),            # first under 50c in minute 13
    "KXETH15M-A": flat(0.6, m8=0.45, m15=0.3),                # under at the entry, then not until minute 15
    "KXBTC15M-B": flat(0.7, m14=0.5, m15=0.55),               # never under 50c: in flipsOf, in no minute
    "KXWTI15M-B": flat(0.95, m10=0.3, m11=0.2, m12=0.1),      # minute 10
    "KXSOL15M-A": flat(m11=0.4),                              # a won bet that dipped: not counted
}                                                             # KXGOLD15M-A lost with no mids: not counted
BACKTEST = {"90-92": 0.1234, "92-94": 0.05, "94+": 0.02}


def live_bets(rows=LIVE):
    out = []
    for i, (ticker, w, side, ask, spread, status, cost, pnl) in enumerate(rows):
        series = ticker.split("-")[0]
        won = status == "won"
        out.append({"id": i + 1, "ticker": ticker, "series": series, "window_open": w, "close_ts": w + 900,
                    "side": side, "price": ask, "contracts": round(cost / ask), "cost": cost, "fee": 0.02,
                    "placed_ts": w + 482 + i, "order_id": f"o{i}", "client_order_id": f"c{i}", "status": status,
                    "result": side if won else ("no" if side == "yes" else "yes"),
                    "payout": round(cost / ask) if won else 0.0, "pnl": pnl, "settled_ts": w + 905, "ask": ask,
                    "spread": spread, "crypto": series not in NOT_CRYPTO})
    return out


@pytest.fixture(scope="module")
def live(ll):
    return ll.live_summary(live_bets(), MIDS, BACKTEST)


def test_live_summary_totals(live):
    assert set(live) == {"from", "to", "bets", "lost", "pnl", "staked", "bands", "wide", "rest", "watch", "flips",
                         "flipsOf", "clusters", "days"}
    assert (live["from"], live["to"]) == (W1, W4 + 900), "the first bet's window_open, the last bet's close_ts"
    assert (live["bets"], live["lost"], live["pnl"], live["staked"]) == (12, 5, -13.54, 112.19), "money to 2 places"
    roundtrip(live)


def test_live_summary_bands_every_one_in_order_even_empty(live):
    bands = live["bands"]
    assert [(b["key"], b["label"]) for b in bands] == [("90-92", "90–92¢"), ("92-94", "92–94¢"), ("94+", "94¢ and up")]
    assert all(set(b) == {"key", "label", "bets", "lost", "pnl", "staked", "implied", "backtest"} for b in bands)
    cheap, mid, dear = bands
    assert (cheap["bets"], cheap["lost"], cheap["pnl"], cheap["staked"]) == (5, 3, -8.06, 41.84)   # 92c counts here
    assert cheap["implied"] == pytest.approx(0.455 / 5) and cheap["backtest"] == 0.1234
    assert (mid["bets"], mid["lost"], mid["pnl"], mid["staked"], mid["implied"]) == (0, 0, 0.0, 0.0, None)
    assert mid["backtest"] == 0.05, "the backtest's share, even with no live bets in the band"
    assert (dear["bets"], dear["lost"], dear["pnl"], dear["staked"]) == (6, 2, -8.06, 48.99)
    assert dear["implied"] == pytest.approx(0.186 / 6) and dear["backtest"] == 0.02
    assert sum(b["bets"] for b in bands) == live["bets"] - 1, "the 89c bet is in no band"


def test_live_summary_wide_and_rest(live):
    assert set(live["wide"]) == set(live["rest"]) == TALLY
    assert live["wide"] == {"bets": 2, "lost": 2, "pnl": -8.3, "staked": 8.25}, "90-92c with a spread over 0.2c"
    assert live["rest"] == {"bets": 10, "lost": 3, "pnl": -5.24, "staked": 103.94}, "every other settled bet"


def test_live_summary_watch(ll, live):
    w = live["watch"]
    assert w == {"bets": 5, "lost": 3, "expected": 0.62, "p": 0.025}       # 5 x 12.34% = 0.617 -> 0.62
    assert w["p"] == round(ll.poisson_tail(3, 0.62), 3) == round(ll.poisson_tail(3, 5 * 0.1234), 3)


def test_live_summary_watch_is_null_without_a_share_or_a_cheap_bet(ll):
    no_share = ll.live_summary(live_bets(), MIDS, {"92-94": 0.05, "94+": 0.02})
    assert no_share["watch"] is None and no_share["bands"][0]["backtest"] is None
    dear_only = ll.live_summary(live_bets([r for r in LIVE if not 0.90 <= r[3] <= 0.92]), MIDS, BACKTEST)
    assert dear_only["watch"] is None
    assert dear_only["bands"][0]["bets"] == 0 and dear_only["bands"][0]["implied"] is None
    assert dear_only["wide"] == {"bets": 0, "lost": 0, "pnl": 0.0, "staked": 0.0}


def test_live_summary_flips(live):
    assert live["flips"] == {"9": 0, "10": 1, "11": 0, "12": 0, "13": 1, "14": 0, "15": 1}
    assert live["flipsOf"] == 4, "the lost bets with mids; the one without isn't counted"


def test_live_summary_clusters(live):
    # W1: BTC and ETH lost (and gold, a metal); W2: BTC lost with WTI (energy) - one crypto loss alone
    assert live["clusters"] == {"cryptoLost": 3, "inMulti": 2}


def test_live_summary_days_by_the_et_date_of_close(live):
    assert live["days"] == [
        {"day": "2026-09-28", "bets": 7, "lost": 5, "pnl": -19.47, "staked": 28.35, "stake": 4.05},  # 23:45 ET too
        {"day": "2026-09-29", "bets": 2, "lost": 0, "pnl": 1.26, "staked": 18.66, "stake": 9.33},
        {"day": "2026-09-30", "bets": 3, "lost": 0, "pnl": 4.68, "staked": 65.18, "stake": 21.73},
    ]


def test_live_summary_with_no_bets(ll):
    s = ll.live_summary([], {}, BACKTEST)
    assert (s["from"], s["to"], s["bets"], s["lost"], s["pnl"], s["staked"]) == (None, None, 0, 0, 0.0, 0.0)
    assert [b["key"] for b in s["bands"]] == ["90-92", "92-94", "94+"]
    assert all(b["bets"] == 0 and b["implied"] is None for b in s["bands"])
    assert s["watch"] is None and s["flipsOf"] == 0 and set(s["flips"].values()) == {0}
    assert s["clusters"] == {"cryptoLost": 0, "inMulti": 0} and s["days"] == []
    assert s["wide"] == s["rest"] == {"bets": 0, "lost": 0, "pnl": 0.0, "staked": 0.0}
    roundtrip(s)


# ------------------------------------------------------------------ rule_test: a synthetic d shaped like common.load()'s
# Each window holds one market per slot: the favourite's side, its own ask and spread, flat from minute 1 to 15.
SLOTS = {
    "A": ("yes", 0.90, 0.001),   # band, kept
    "B": ("yes", 0.91, 0.005),   # band, skipped
    "C": ("no", 0.92, 0.003),    # band (92c inclusive), skipped: 0.3c is wide; a NO favourite
    "D": ("yes", 0.92, 0.002),   # band, kept: 0.2c is not wide
    "E": ("yes", 0.93, 0.004),   # out of the band: the family's 93c and 94c tops only
    "F": ("no", 0.94, 0.010),    # the family's 94c top only, and the only bet over a 0.9c spread
    "G": ("yes", 0.96, 0.001),   # the live rule only
}
REFUSED = {                      # markets the live rule mustn't bet
    "cheap": ("yes", 0.89, 0.001),     # under 90c
    "spready": ("yes", 0.91, 0.020),   # a 2c spread: its spread sign
    "late": ("yes", 0.91, 0.002),      # 45c until minute 7: its late sign
}
GROUP = {"A": "crypto", "B": "crypto", "C": "metals", "D": "crypto", "E": "energy", "F": "crypto", "G": "crypto",
         "cheap": "crypto", "spready": "metals", "late": "crypto"}
# A slot loses in the windows whose index is a multiple of this (None: never). On pre, B loses most (35%), so every
# family row skipping B alone ties lowest and the first of them, (91c, 0.1c), is chosen; on post F loses most and only
# (94c, 0.9c) skips F alone. In the base, B wins every post bet: one scored hi is above 0 and one below, so it doesn't
# hold. In HOLDS, B also loses a quarter of its post bets: both scored hi are below 0.
BASE = {"pre": {"A": None, "B": 3, "C": 10, "D": 20, "E": 8, "F": 4, "G": 15},
        "post": {"A": None, "B": None, "C": 12, "D": 20, "E": 9, "F": 3, "G": 15}}
HOLDS = {"pre": BASE["pre"], "post": {**BASE["post"], "B": 4}}
FAMILY_SETS = {
    (0.91, None): "AB", (0.91, 0.001): "B", (0.91, 0.002): "B", (0.91, 0.004): "B", (0.91, 0.009): "",
    (0.92, None): "ABCD", (0.92, 0.001): "BCD", (0.92, 0.002): "BC", (0.92, 0.004): "B", (0.92, 0.009): "",
    (0.93, None): "ABCDE", (0.93, 0.001): "BCDE", (0.93, 0.002): "BCE", (0.93, 0.004): "B", (0.93, 0.009): "",
    (0.94, None): "ABCDEF", (0.94, 0.001): "BCDEF", (0.94, 0.002): "BCEF", (0.94, 0.004): "BF", (0.94, 0.009): "F",
}
FIRST, LAST = utc("2026-01-05T02:00"), utc("2026-10-08T23:45")


def yes_quotes(side, ask, spread):
    """(YES bid, YES ask) giving that side its own ask and spread."""
    if side == "yes":
        return round(ask - spread, 4), round(ask, 4)
    return round(1 - ask, 4), round(1 - ask + spread, 4)


def build_d(pattern, n=40):
    """(d, info): markets as common.load() gives them, sorted by open time, and each one's slot and half ("pre",
    "post", or "fed" / "edge" for the windows the live rule mustn't bet)."""
    rows = []

    def add(t, slot, half, lose):
        side, ask, spread = SLOTS.get(slot) or REFUSED[slot]
        b, a = yes_quotes(side, ask, spread)
        bid, ask_ = [b] * 15, [a] * 15
        if slot == "late":
            bid[:7], ask_[:7] = [0.44] * 7, [0.46] * 7
        won = not lose
        rows.append({"ticker": f"KX{slot.upper()}15M-{int(t)}", "series": f"KX{slot.upper()}15M", "group": GROUP[slot],
                     "open_ts": int(t), "yes": int(won if side == "yes" else not won), "bid": bid, "ask": ask_,
                     "info": SimpleNamespace(slot=slot, half=half, lost=lose)})

    halves = {"pre": [FIRST + i * 86400 for i in range(n)],                           # Jan 5 on, 9 pm ET
              "post": [utc("2026-07-18T06:00") + 2 * i * 86400 for i in range(n)]}    # Jul 18 to Oct 4
    for half, times in halves.items():
        for i, t in enumerate(times):
            for slot in SLOTS:
                every = pattern[half][slot]
                add(t, slot, half, every is not None and i % every == 0)
            for slot in REFUSED:
                add(t, slot, half, False)
    for t in (utc("2026-01-28T19:15"), utc("2026-09-16T18:30")):    # 2:15 pm ET Jan 28, 2:30 pm ET Sep 16: Fed
        for slot in SLOTS:
            add(t, slot, "fed", True)
    for t in (utc("2026-07-17T23:45"), utc("2026-07-18T00:00"), LAST):   # each side of Jul 18, and the last window
        add(t, "cheap", "edge", False)
    rows.sort(key=lambda r: r["open_ts"])
    d = {"ticker": np.array([r["ticker"] for r in rows]), "series": np.array([r["series"] for r in rows]),
         "group": np.array([r["group"] for r in rows]), "open_ts": np.array([r["open_ts"] for r in rows], np.int64),
         "yes": np.array([r["yes"] for r in rows], np.int8)}
    for k in ("bid", "ask"):
        d[k] = np.round(np.array([r[k] for r in rows], np.float64), 4)
    d["last"] = np.round((d["bid"] + d["ask"]) / 2, 4)
    return d, [r["info"] for r in rows]


def slots(info, names):
    """The markets of these slots in the windows the live rule may bet."""
    return np.array([r.slot in names and r.half in ("pre", "post") for r in info])


def expected(lab, d, mask, keys=("pre", "post", "all")):
    """{period: S} for the markets in mask, from common.summary and edge_map.run_bets."""
    C, E = lab.C, lab.E
    _, sy, top = C.live_rule(d)
    pnl, cost, t, wins, price = E.run_bets(d, mask, top, C.won(d, sy))
    p = C.period_of(t)
    sel = {"pre": p == "pre", "post": np.isin(p, ("before", "build", "paper")), "all": np.ones(len(t), bool)}
    out = {}
    for k in keys:
        s = sel[k]
        x = C.summary(pnl[s], cost[s], t[s])
        if x["bets"]:
            x.update(lost=float(1 - wins[s].mean()), implied=float((1 - price[s]).mean()))
        else:
            x = {**dict.fromkeys(S_KEYS), "bets": 0}
        out[k] = x
    return out


def same(got, want, where=""):
    assert set(got) == S_KEYS, where
    assert got["bets"] == want["bets"], where
    for k in S_KEYS - {"bets"}:
        if want[k] is None:
            assert got[k] is None, (where, k)
        else:
            assert got[k] == pytest.approx(want[k], rel=1e-9, abs=1e-9), (where, k)


@pytest.fixture(scope="module")
def base(ll):
    d, info = build_d(BASE)
    rule, backtest = ll.rule_test(d)
    return SimpleNamespace(d=d, info=info, rule=rule, backtest=backtest)


def test_the_synthetic_markets_are_what_the_live_rule_bets(lab, base):
    m, _, _ = lab.C.live_rule(base.d)
    assert (m == slots(base.info, "ABCDEFG")).all(), "the refused markets and the Fed windows are not bets"
    assert lab.C.period_of(base.d["open_ts"][m]).tolist().count("pre") == 7 * 40


def test_rule_test_header(ll, base):
    r = base.rule
    assert set(r) == {"lo", "hi", "spread", "slip", "start", "from", "to", "periods", "rows", "family", "holdout",
                      "holds", "sizing"}
    assert (r["lo"], r["hi"], r["spread"], r["slip"], r["start"]) == (0.90, 0.92, 0.002, 0.004, 500.0)
    assert (r["from"], r["to"]) == (FIRST, LAST + 900), "d's first open, its last open + 900"
    roundtrip(r)
    json.dumps(base.backtest, allow_nan=False)


def test_rule_test_periods_label_the_datas_own_dates(base):
    # UTC dates: 2 am UTC Jan 5 is Jan 4 in ET, midnight UTC Jul 18 is Jul 17 in ET; the last window ends Oct 9 00:00
    assert base.rule["periods"] == [{"key": "pre", "label": "Jan 5 – Jul 17"},
                                    {"key": "post", "label": "Jul 18 – Oct 8"},
                                    {"key": "all", "label": "Jan 5 – Oct 8"}]


@pytest.mark.parametrize("row, names", [("skipped", "BC"), ("kept", "AD"), ("band", "ABCD"), ("live", "ABCDEFG")])
def test_rule_test_rows(lab, base, row, names):
    """skipped: 90-92c inclusive and a spread over 0.2c (92c at 0.3c is skipped, 92c at 0.2c kept)."""
    got = base.rule["rows"][row]
    assert set(got) == {"pre", "post", "all"}
    want = expected(lab, base.d, slots(base.info, names))
    for k in ("pre", "post", "all"):
        same(got[k], want[k], f"{row} {k}")
    assert got["all"]["bets"] == len(names) * 80 and got["pre"]["bets"] == got["post"]["bets"] == len(names) * 40


def test_rule_test_family_twenty_rows_in_order(lab, base):
    fam = base.rule["family"]
    assert [(f["hi"], f["spread"]) for f in fam] == FAMILY_ORDER
    for f in fam:
        assert set(f) == {"hi", "spread", "pre", "post"}
        names = FAMILY_SETS[(f["hi"], f["spread"])]
        want = expected(lab, base.d, slots(base.info, names), ("pre", "post"))
        for k in ("pre", "post"):
            same(f[k], want[k], f"family {f['hi']} {f['spread']} {k}")
    assert fam[4]["pre"] == {**dict.fromkeys(S_KEYS), "bets": 0}, "no bets: bets 0 and every other field None"


def test_rule_test_holdout_picks_the_lowest_mu_ties_to_the_first(base):
    fam, hold = base.rule["family"], base.rule["holdout"]
    lone_b = [f["pre"]["mu"] for f in fam if FAMILY_SETS[(f["hi"], f["spread"])] == "B"]
    assert len(lone_b) == 5 and len(set(lone_b)) == 1, "five rows tie on pre"
    by = {(f["hi"], f["spread"]): f for f in fam}
    assert [{k: h[k] for k in ("chosenOn", "scoredOn", "hi", "spread")} for h in hold] == [
        {"chosenOn": "pre", "scoredOn": "post", "hi": 0.91, "spread": 0.001},
        {"chosenOn": "post", "scoredOn": "pre", "hi": 0.94, "spread": 0.009}]
    for h in hold:
        assert set(h) == {"chosenOn", "scoredOn", "hi", "spread", "chosen", "scored"}
        row = by[(h["hi"], h["spread"])]
        assert h["chosen"] == row[h["chosenOn"]] and h["scored"] == row[h["scoredOn"]]
        assert h["chosen"]["mu"] == min(f[h["chosenOn"]]["mu"] for f in fam if f[h["chosenOn"]]["bets"])


def test_rule_test_holds_only_when_every_scored_hi_is_below_zero(ll, base):
    pre_pick, post_pick = base.rule["holdout"]
    assert pre_pick["scored"]["hi"] > 0 > post_pick["scored"]["hi"], "the base case: one below, one above"
    assert base.rule["holds"] is False
    rule, _ = ll.rule_test(build_d(HOLDS)[0])
    assert [(h["hi"], h["spread"]) for h in rule["holdout"]] == [(0.91, 0.001), (0.94, 0.009)]
    assert all(h["scored"]["hi"] < 0 for h in rule["holdout"]) and rule["holds"] is True
    rule, _ = ll.rule_test(build_d(HOLDS, n=5)[0])
    assert all(h["scored"]["hi"] is None for h in rule["holdout"]), "too few bets for a range"
    assert rule["holds"] is False


def test_rule_test_sizing_is_edge_maps_replay_over_each_period_alone(lab, base):
    C, E = lab.C, lab.E
    d = base.d
    _, sy, top = C.live_rule(d)
    w = C.won(d, sy)
    p = C.period_of(d["open_ts"])
    sel = {"all": np.ones(len(p), bool), "pre": p == "pre", "post": np.isin(p, ("before", "build", "paper"))}
    masks = {"live": slots(base.info, "ABCDEFG"), "skip": slots(base.info, "ADEFG")}
    sizing = base.rule["sizing"]
    assert {k: set(v) for k, v in sizing.items()} == {"live": {"all", "pre", "post"}, "skip": {"all", "pre", "post"}}
    for name, mask in masks.items():
        for k, s in sel.items():
            assert sizing[name][k] == E.replay(d, mask & s, top, w), (name, k)
    assert sizing["live"]["all"]["start"] == 500.0 and sizing["live"]["all"]["bets"] == 7 * 80


def test_rule_test_gives_the_backtests_loss_share_per_band(base):
    def share(names):
        got = [r for r in base.info if r.slot in names and r.half in ("pre", "post")]
        return sum(r.lost for r in got) / len(got)
    assert set(base.backtest) == {"90-92", "92-94", "94+"}
    for key, names in (("90-92", "ABCD"), ("92-94", "EF"), ("94+", "G")):   # 92c is 90-92 and 94c is 92-94
        assert base.backtest[key] == pytest.approx(share(names), abs=1e-12), key


# ------------------------------------------------------------------ fetch_paths: a fake get as Kalshi answers
MISSING = object()


def block(x):
    """A candle's quote block: a number is its close_dollars (a string, as Kalshi sends it), a dict is as given."""
    if isinstance(x, dict):
        return x
    return {} if x is None else {"close_dollars": f"{x:.4f}"}


def candle(w, k, b=None, a=None, p=None, end=None):
    c = {"end_period_ts": int(w) + 60 * k if end is None else end}
    for key, v in (("yes_bid", b), ("yes_ask", a), ("price", p)):
        if v is not MISSING:
            c[key] = block(v)
    return c


class FakeGet:
    """backtest_large.get as Kalshi's batch candlesticks endpoint answers: each asked ticker with its candles, or a
    whole window's reply replaced (None for a failed request, {} for an empty one). Every call is kept."""

    def __init__(self, candles=None, replies=None):
        self.candles, self.replies, self.calls = candles or {}, replies or {}, []

    def __call__(self, url, params=None, **kwargs):
        self.calls.append((url, dict(params or {})))
        if params["start_ts"] in self.replies:
            return self.replies[params["start_ts"]]
        return {"markets": [{"market_ticker": t, "candlesticks": self.candles.get(t, [])}
                            for t in params["market_tickers"].split(",")], "cursor": ""}


def path_bet(ticker, window):
    return {"ticker": ticker, "series": ticker.split("-")[0], "window_open": float(window),
            "close_ts": float(window + 900), "side": "yes", "status": "lost"}


def read_cache(path):
    """The cache's header and its rows as (ticker, k, b, a, p), numbers parsed and "" read as None."""
    with open(path, newline="", encoding="utf-8") as fh:
        lines = list(csv.reader(fh))
    num = lambda x: None if x == "" else float(x)  # noqa: E731
    return lines[0], [(t, int(k), num(b), num(a), num(p)) for t, k, b, a, p in lines[1:]]


def as_tuples(rows):
    return sorted((r["ticker"], r["k"], r["b"], r["a"], r["p"]) for r in rows)


P1 = int(et("2026-10-01T10:00"))
P2, P3 = P1 + 900, P1 + 1800


def test_fetch_paths_fetches_only_uncached_windows_20_tickers_a_call(ll, study, tmp_path):
    big = [f"KXBTC15M-W1-{i:02d}" for i in range(21)]              # 21 markets in one window: two calls
    bets = ([path_bet(t, P1) for t in big] + [path_bet(t, P2) for t in ("KXETH15M-W2-A", "KXSOL15M-W2-B")]
            + [path_bet(t, P3) for t in ("KXXRP15M-W3-A", "KXDOGE15M-W3-B")])
    cache = tmp_path / "live_losses_paths.csv"
    old = "ticker,k,b,a,p\r\nKXXRP15M-W3-A,8,0.9,0.91,\r\n"       # W3 has a row for one market: cached
    cache.write_text(old, encoding="utf-8", newline="")
    candles = {t: [candle(P1, 8, 0.91, 0.92, 0.915)] for t in big}
    candles.update({"KXETH15M-W2-A": [candle(P2, 7, 0.93, 0.94, 0.93), candle(P2, 8, 0.94, 0.95, 0.95)],
                    "KXSOL15M-W2-B": [candle(P2, 8, 0.95, 0.96, None)],
                    "KXDOGE15M-W3-B": [candle(P3, 8, 0.5, 0.5, 0.5)]})
    get = FakeGet(candles)
    rows = ll.fetch_paths(bets, str(cache), get)

    url = study.backtest_large.BASE + "/markets/candlesticks"
    assert all(u == url for u, _ in get.calls)
    for _, params in get.calls:
        assert set(params) == {"market_tickers", "start_ts", "end_ts", "period_interval"}
        assert type(params["start_ts"]) is int and params["end_ts"] == params["start_ts"] + 900, "whole seconds"
        assert params["period_interval"] == 1 and len(params["market_tickers"].split(",")) <= 20
    by_window = {}
    for _, params in get.calls:
        by_window.setdefault(params["start_ts"], []).append(params["market_tickers"].split(","))
    assert set(by_window) == {P1, P2}, "W3 is cached and not fetched again"
    assert sorted(len(x) for x in by_window[P1]) == [1, 20]
    assert sorted(t for x in by_window[P1] for t in x) == big, "each market once"
    assert by_window[P2] == [["KXETH15M-W2-A", "KXSOL15M-W2-B"]]

    new = ([{"ticker": t, "k": 8, "b": 0.91, "a": 0.92, "p": 0.915} for t in big]
           + [{"ticker": "KXETH15M-W2-A", "k": 7, "b": 0.93, "a": 0.94, "p": 0.93},
              {"ticker": "KXETH15M-W2-A", "k": 8, "b": 0.94, "a": 0.95, "p": 0.95},
              {"ticker": "KXSOL15M-W2-B", "k": 8, "b": 0.95, "a": 0.96, "p": None}])
    cached = [{"ticker": "KXXRP15M-W3-A", "k": 8, "b": 0.9, "a": 0.91, "p": None}]
    key = lambda r: (r["ticker"], r["k"])  # noqa: E731
    assert sorted(rows, key=key) == sorted(cached + new, key=key)
    text = cache.read_bytes().decode("utf-8")
    assert text.startswith(old), "appended: the rows already there are left as they were"
    header, saved = read_cache(cache)
    assert header == ["ticker", "k", "b", "a", "p"] and text.count("ticker,k,b,a,p") == 1
    assert sorted(saved) == as_tuples(cached + new)


def test_fetch_paths_creates_the_cache_with_its_header(ll, tmp_path):
    cache = tmp_path / "paths.csv"
    rows = ll.fetch_paths([path_bet("KXBTC15M-X", P1)], str(cache), FakeGet({"KXBTC15M-X": [candle(P1, 9, 0.9, 0.92)]}))
    assert rows == [{"ticker": "KXBTC15M-X", "k": 9, "b": 0.9, "a": 0.92, "p": None}]
    assert read_cache(cache) == (["ticker", "k", "b", "a", "p"], [("KXBTC15M-X", 9, 0.9, 0.92, None)])
    assert cache.read_text(encoding="utf-8").splitlines()[1].endswith(",")       # None is written as ""


def test_fetch_paths_tries_a_failed_window_again_next_run(ll, tmp_path):
    bets = [path_bet("KXBTC15M-F1", P1), path_bet("KXBTC15M-F2", P2), path_bet("KXBTC15M-OK", P3)]
    candles = {"KXBTC15M-F1": [candle(P1, 8, 0.9, 0.91, 0.9)], "KXBTC15M-F2": [candle(P2, 8, 0.92, 0.93, 0.92)],
               "KXBTC15M-OK": [candle(P3, 8, 0.94, 0.95, 0.94)]}
    cache = tmp_path / "paths.csv"
    first = ll.fetch_paths(bets, str(cache), FakeGet(candles, replies={P1: None, P2: {}}))
    assert [r["ticker"] for r in first] == ["KXBTC15M-OK"], "a failed or empty reply adds nothing"
    assert {row[0] for row in read_cache(cache)[1]} == {"KXBTC15M-OK"}
    get = FakeGet(candles)
    again = ll.fetch_paths(bets, str(cache), get)
    assert sorted(p["start_ts"] for _, p in get.calls) == [P1, P2], "only the two that failed"
    assert sorted(r["ticker"] for r in again) == ["KXBTC15M-F1", "KXBTC15M-F2", "KXBTC15M-OK"]
    get = FakeGet(candles)
    assert len(ll.fetch_paths(bets, str(cache), get)) == 3 and get.calls == [], "everything cached now"


def test_fetch_paths_reads_close_then_previous_and_k_from_the_candles_end(ll, tmp_path):
    t = "KXETH15M-FIELDS"
    candles = [
        candle(P1, 1, {"close_dollars": "0.9100", "previous_dollars": "0.5000"}, 0.93, 0.92),    # close wins
        candle(P1, 2, {"previous_dollars": "0.9200"}, {"close_dollars": None, "previous_dollars": "0.9400"}, {}),
        candle(P1, 0, MISSING, {"close_dollars": "0.9500"}, {"previous_dollars": "0.9300"}, end=P1 + 3 * 60 + 59),
    ]
    cache = tmp_path / "paths.csv"
    rows = ll.fetch_paths([path_bet(t, P1)], str(cache), FakeGet({t: candles}))
    assert sorted(rows, key=lambda r: r["k"]) == [
        {"ticker": t, "k": 1, "b": 0.91, "a": 0.93, "p": 0.92},
        {"ticker": t, "k": 2, "b": 0.92, "a": 0.94, "p": None},
        {"ticker": t, "k": 3, "b": None, "a": 0.95, "p": 0.93}]                  # (end - window) // 60
    assert all(type(r["k"]) is int for r in rows)
    assert sorted(read_cache(cache)[1]) == [(t, 1, 0.91, 0.93, 0.92), (t, 2, 0.92, 0.94, None), (t, 3, None, 0.95, 0.93)]


def test_fetch_paths_gives_cached_rows_back_as_numbers(ll, tmp_path):
    cache = tmp_path / "paths.csv"
    text = "ticker,k,b,a,p\r\nKXBTC15M-C,1,0.9,0.92,\r\nKXBTC15M-C,2,,,0.91\r\n"
    cache.write_text(text, encoding="utf-8", newline="")
    get = FakeGet()
    rows = ll.fetch_paths([path_bet("KXBTC15M-C", P1)], str(cache), get)
    assert sorted(rows, key=lambda r: r["k"]) == [{"ticker": "KXBTC15M-C", "k": 1, "b": 0.9, "a": 0.92, "p": None},
                                                  {"ticker": "KXBTC15M-C", "k": 2, "b": None, "a": None, "p": 0.91}]
    assert all(type(r["k"]) is int for r in rows)
    assert get.calls == [] and cache.read_bytes().decode("utf-8") == text


# ------------------------------------------------------------------ main
@pytest.fixture
def files(ll, monkeypatch, tmp_path):
    """main's cache and output moved to a temp folder."""
    out, cache = tmp_path / "live_losses.json", tmp_path / "live_losses_paths.csv"
    monkeypatch.setattr(ll, "OUT", str(out))
    monkeypatch.setattr(ll, "CACHE", str(cache))
    return SimpleNamespace(out=out, cache=cache)


def stub_get(ll, study, monkeypatch, get):
    monkeypatch.setattr(study.backtest_large, "get", get)
    monkeypatch.setattr(ll, "get", get, raising=False)    # in case it was imported by name


def test_main_writes_live_losses_json(ll, lab, study, files, monkeypatch):
    bets = live_bets()
    rows = [{"ticker": "KXBTC15M-A", "k": k, "b": None, "a": None, "p": 0.9 if k < 13 else 0.3} for k in range(1, 16)]
    rows += [{"ticker": "KXETH15M-A", "k": k, "b": 0.5, "a": 0.6, "p": None} for k in (8, 9)]   # NO: 45c from minute 8
    d, _ = build_d(BASE, n=12)
    seen = {"load": 0}

    def read_bets(path):
        seen["read"] = path
        return [dict(b) for b in bets]

    def fetch_paths(b, cache, get):
        seen["fetch"] = (b, cache, get)
        return rows

    def load(*args, **kwargs):
        seen["load"] += 1
        return d
    get = FakeGet()
    monkeypatch.setattr(ll, "read_bets", read_bets)
    monkeypatch.setattr(ll, "fetch_paths", fetch_paths)
    monkeypatch.setattr(lab.C, "load", load)
    stub_get(ll, study, monkeypatch, get)
    before = time.time()
    ll.main()
    after = time.time()

    saved = strict(files.out.read_text(encoding="utf-8"))
    assert set(saved) == {"asOf", "live", "rule"}
    assert before <= saved["asOf"] <= after
    assert os.fspath(seen["read"]) == os.fspath(ll.LEDGER) and seen["load"] == 1
    assert seen["fetch"][0] == bets and os.fspath(seen["fetch"][1]) == str(files.cache) and seen["fetch"][2] is get
    rule, backtest = ll.rule_test(d)
    mids = ll.fav_mids(rows, {b["ticker"]: b["side"] for b in bets})
    assert saved["live"] == roundtrip(ll.live_summary(bets, mids, backtest))
    assert saved["rule"] == roundtrip(rule)
    assert saved["live"]["flipsOf"] == 2 and saved["live"]["flips"]["9"] == 1 and saved["live"]["flips"]["13"] == 1
    assert get.calls == []


def test_main_end_to_end_on_a_temp_ledger(ll, lab, study, files, monkeypatch, tmp_path):
    w = et("2026-10-02T11:00")
    bets = [ledger_bet("KXBTC15M-E2E-1", "lost", w + 481, 0.91, window=w),
            ledger_bet("KXETH15M-E2E-2", "won", w + 482, 0.95, window=w),
            ledger_bet("KXSOL15M-E2E-3", "open", w + 483, 0.93, window=w)]
    path = write_ledger(tmp_path / "state" / "live-prod.db", bets,
                        [decision("KXBTC15M-E2E-1", 0.905, 0.91, 0.91), decision("KXETH15M-E2E-2", 0.948, 0.95, 0.95)])
    monkeypatch.setattr(ll, "LEDGER", str(path))
    d, _ = build_d(BASE, n=12)
    monkeypatch.setattr(lab.C, "load", lambda *a, **k: d)
    get = FakeGet({"KXBTC15M-E2E-1": [candle(w, k, 0.9 if k < 14 else 0.2, 0.92 if k < 14 else 0.3) for k in range(1, 16)],
                   "KXETH15M-E2E-2": [candle(w, 8, 0.94, 0.95)]})
    stub_get(ll, study, monkeypatch, get)
    ll.main()
    saved = strict(files.out.read_text(encoding="utf-8"))
    live = saved["live"]
    assert (live["bets"], live["lost"], live["flipsOf"], live["flips"]["14"]) == (2, 1, 1, 1)
    assert live["bands"][0]["bets"] == 1 and live["days"][0]["day"] == "2026-10-02"
    assert [sorted(p["market_tickers"].split(",")) for _, p in get.calls] == [["KXBTC15M-E2E-1", "KXETH15M-E2E-2"]]
    assert files.cache.exists() and saved["rule"] == roundtrip(ll.rule_test(d)[0])


def test_main_with_no_ledger_yet(ll, lab, study, files, monkeypatch, tmp_path):
    monkeypatch.setattr(ll, "LEDGER", str(tmp_path / "state" / "live-prod.db"))
    d, _ = build_d(BASE, n=12)
    monkeypatch.setattr(lab.C, "load", lambda *a, **k: d)
    get = FakeGet()
    stub_get(ll, study, monkeypatch, get)
    ll.main()
    saved = strict(files.out.read_text(encoding="utf-8"))
    assert saved["live"]["bets"] == 0 and saved["live"]["days"] == [] and saved["rule"]["family"]
    assert get.calls == []
