"""The +1¢ limit on paper, in the Live Research tab's server side (GET /api/live-research). Real orders go back to a
limit at exactly the ask the bot saw (bot.LIMIT_UP is 0); after each one the bot reads the order book and writes down
what a limit 1¢ higher (bot.SHADOW_UP) would have bought on top of the real fill, the "extra" contracts, in the ledger's
shadow table (kind 'limitup'; another paper experiment, "fast entry", will share the table with kind 'fast'). Paper
means no money moves: the contracts are only measured, then settled with the market like real bets.

live_research() reads those rows into a "shadow" block: how many orders were measured and how many book reads failed
("unread"), the real fill share against the fill share with the extra cent, the median lag (how many seconds after
minute 8 the book was read), the extra contracts' price, win rate, P&L and ¢ per $10 with its standard error clustered
by window (bets in one 15-minute window share their luck, so the window is the unit), a verdict, and the latest rows.
With no shadow table (a ledger from before the restart) the block is null. The live card gains an "off" state: while
bot.LIMIT_UP is 0 and no order ever had a limit over the ask it saw, there is no live experiment to wait for.

Every ledger here is built with explicit CREATE TABLE statements (the shadow table as the bot creates it), not
bot.connect(), so they stay the same when bot.connect() changes. Each number is worked out by hand in the test. The
ledger is opened read-only and never changed. Nothing here touches the network or the real research files.

    python -m pytest tests/test_shadow_api.py -q
"""
import json
import os
import sqlite3
import time

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, home, serving  # noqa: F401  (home is a fixture)
from test_live_research_api import (EMPTY_GROUP, FILLS, GROUP_KEYS, OLD_SCHEMA, W1, W2, W3, W4, WA, WB, WAITING,
                                    clustered_se, get, same, trade)

# The paper experiments' table: one row per (kind, ticker).
SHADOW = ("CREATE TABLE IF NOT EXISTS shadow (id INTEGER PRIMARY KEY, kind TEXT, ticker TEXT, ts REAL, window_open REAL,"
          " close_ts REAL, series TEXT, side TEXT, seen REAL, limit_price REAL, asked REAL, filled REAL, lag REAL, extra REAL,"
          " cost REAL, fee REAL, status TEXT, result TEXT, pnl REAL, settled_ts REAL, UNIQUE(kind, ticker))")

# The live card's new state, and the paper card's verdicts, word for word
OFF = "Off: real orders go at the ask the bot saw. The paper +1¢ above measures the extra cent without real money."
S_WAITING = "Not recording yet: the bot measures the paper +1¢ from its next restart."
S_TOO_EARLY = "Too early to tell: {n} orders measured on paper so far. The verdict comes on Nov 27, after 6 weeks."
S_THIN = "Not enough extra contracts to tell yet: {n} orders measured on paper."
S_HELPING = "On paper the extra cent pays: the extra contracts made money, and their 95% range is above zero."
S_HURTING = "On paper the extra cent loses money: the extra contracts' 95% range is below zero."
S_NO_DIFFERENCE = "No clear difference on paper: the extra contracts' 95% range includes zero."

SHADOW_KEYS = {"limitUp", "started", "until", "orders", "unread", "asked", "filled", "extra", "fillShare", "fillShareWith",
               "remaining", "extraShare", "ordersWithExtra", "lag", "group", "verdict", "rows"}
ROW_KEYS = {"ts", "ticker", "side", "seen", "limit", "asked", "filled", "extra", "avgPrice", "lag", "result"}
UNTIL = 1795766400   # the paper +1¢ runs until Nov 27, 2026, 12:00 AM PT (test_paper_six_weeks.py)


def ahead(monkeypatch):
    """The paper +1¢'s date still to come, whenever the tests run: its verdict is too early to tell."""
    monkeypatch.setattr(dashboard, "SHADOW_UNTIL", time.time() + 86400)


def past(monkeypatch):
    """... or gone by: the 95% range decides."""
    monkeypatch.setattr(dashboard, "SHADOW_UNTIL", time.time() - 1)


@pytest.fixture(autouse=True)
def no_real_research(tmp_path_factory, monkeypatch):
    """No test reads the real research folder (the reply's predictions come from it): each gets an empty one."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path_factory.mktemp("research")))


# ------------------------------------------------------------------ building a ledger
def paper_ledger(home, shadow=True, fills=True, name="live-prod"):
    """A mode's ledger as the bot makes it from this restart (its tables before the +1c restart, the fills table, the
    shadow table), or without the shadow table (shadow=False) or the fills table (fills=False) as older ledgers are."""
    db = sqlite3.connect(str(home.dir / f"{name}.db"))
    db.executescript(OLD_SCHEMA)
    if fills:
        db.execute(FILLS)
    if shadow:
        db.execute(SHADOW)
    db.execute("INSERT INTO meta VALUES ('start', '100.0')")
    db.commit()
    return db


def paper(db, ts, ticker, window, seen, asked, filled, extra=0, cost=0.0, fee=0.0, side="yes", result=None, lag=2.4,
          unread=False, kind="limitup"):
    """One shadow row as the bot writes it and settles it: the real order asked for `asked` contracts at the ask it saw
    (seen) and its bet got `filled`; on paper a limit 1c higher would have bought `extra` more for `cost`, plus `fee`.
    The book was read `lag` seconds after minute 8. result: the market's result ("yes"/"no") once settled, None while
    open. unread: the book couldn't be read, so nothing was measured (extra, cost and fee are NULL). A settled row's P&L:
    the extra contracts pay $1 each if its side won, less what they cost and their fee."""
    status = "unread" if unread else "open" if result is None else "settled"
    if unread:
        extra = cost = fee = None
    pnl = (extra if side == result else 0) - cost - fee if status == "settled" else None
    db.execute("INSERT INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price, asked, filled,"
               " lag, extra, cost, fee, status, result, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (kind, ticker, ts, window, window + 900, ticker.split("-")[0], side, seen, min(round(seen + 0.01, 4), 0.999),
                asked, filled, lag, extra, cost, fee, status, result if status == "settled" else None, pnl,
                window + 960 if status == "settled" else None))


def measured(home, unread=True, name="live-prod", also=None):
    """A ledger of paper +1c measurements over five windows, oldest first. Two rows bought nothing extra (all filled for
    real, or no offer in the cent over the ask), two are still open, one lost; two book reads failed (unread), one of
    them the newest row. also(db): more rows to add in between (another kind's), before it's committed."""
    db = paper_ledger(home, name=name)
    paper(db, WB + 482, "KXETH15M-B", WB, 0.95, 10, 10, result="yes", lag=2.5)                    # nothing extra, won
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 6, 3, 3 * 0.96, 0.02, result="yes", lag=2.4)
    paper(db, W1 + 482, "KXETH15M-1", W1, 0.93, 10, 10, side="no", result="yes", lag=2.6)         # nothing extra, lost
    paper(db, W1 + 483, "KXSOL15M-1", W1, 0.96, 12, 4, 5, 2 * 0.965 + 3 * 0.97, 0.03, result="no", lag=3.1)   # lost
    paper(db, W2 + 482, "KXBTC15M-2", W2, 0.94, 8, 2, 4, 4 * 0.95, 0.02, side="no", result="no", lag=1.9)
    if unread:
        paper(db, W2 + 482, "KXETH15M-2", W2, 0.92, 10, 3, lag=30.0, unread=True)
    paper(db, W3 + 482, "KXXRP15M-3", W3, 0.97, 10, 7, 2, 2 * 0.98, 0.01, result="yes", lag=2.2)
    if also:
        also(db)
    paper(db, W4 + 482, "KXSOL15M-4", W4, 0.95, 10, 5, 2, 2 * 0.96, 0.01, side="no", lag=2.8)     # open
    paper(db, W4 + 483, "KXBTC15M-4", W4, 0.90, 10, 0, 6, 6 * 0.91, 0.03, lag=2.0)                # open; got nothing for real
    if unread:
        paper(db, W4 + 484, "KXDOGE15M-4", W4, 0.95, 10, 0, lag=None, unread=True)
    db.commit()
    return db


# Its numbers by hand. Measured rows: all but the two unread ones.
COUNTS = {"started": WB + 482, "until": UNTIL, "orders": 8, "unread": 2,
          "asked": 10 + 10 + 10 + 12 + 8 + 10 + 10 + 10, "filled": 10 + 6 + 10 + 4 + 2 + 7 + 5 + 0,
          "extra": 3 + 5 + 4 + 2 + 2 + 6, "fillShare": 44 / 80, "fillShareWith": (44 + 22) / 80,
          "remaining": 0 + 4 + 0 + 8 + 6 + 3 + 5 + 10, "extraShare": 22 / 36, "ordersWithExtra": 6}
COST = 3 * 0.96 + (2 * 0.965 + 3 * 0.97) + 4 * 0.95 + 2 * 0.98 + 2 * 0.96 + 6 * 0.91       # the extra contracts': 20.86
FEE = 0.02 + 0.03 + 0.02 + 0.01 + 0.01 + 0.03
# Each settled window's (P&L, staked) over its rows with extra contracts: W1 (one won, one lost), W2, W3. The window
# before W1 settled too, but nothing extra was bought in it; W4 is still open.
WINDOWS = [(3 * (1 - 0.96) - 0.02 + (-(2 * 0.965 + 3 * 0.97) - 0.03), 3 * 0.96 + 2 * 0.965 + 3 * 0.97),
           (4 * (1 - 0.95) - 0.02, 4 * 0.95),
           (2 * (1 - 0.98) - 0.01, 2 * 0.98)]
GROUP = {"orders": 6, "contracts": 22, "avgPrice": COST / 22, "fee": FEE, "breakEven": COST / 22 + FEE / 22,
         "settled": 3 + 5 + 4 + 2, "won": 3 + 4 + 2, "winRate": 9 / 14,
         "pnl": 0.10 - 4.87 + 0.18 + 0.03, "staked": 2.88 + 4.84 + 3.80 + 1.96,
         "perTen": 1000 * (0.10 - 4.87 + 0.18 + 0.03) / (2.88 + 4.84 + 3.80 + 1.96), "windows": 3}
# The measured rows, newest first (two at the same moment: the one written later first)
ROWS = [
    {"ts": W4 + 483, "ticker": "KXBTC15M-4", "side": "yes", "seen": 0.90, "limit": 0.91, "asked": 10, "filled": 0,
     "extra": 6, "avgPrice": 0.91, "lag": 2.0, "result": "open"},
    {"ts": W4 + 482, "ticker": "KXSOL15M-4", "side": "no", "seen": 0.95, "limit": 0.96, "asked": 10, "filled": 5,
     "extra": 2, "avgPrice": 0.96, "lag": 2.8, "result": "open"},
    {"ts": W3 + 482, "ticker": "KXXRP15M-3", "side": "yes", "seen": 0.97, "limit": 0.98, "asked": 10, "filled": 7,
     "extra": 2, "avgPrice": 0.98, "lag": 2.2, "result": "won"},
    {"ts": W2 + 482, "ticker": "KXBTC15M-2", "side": "no", "seen": 0.94, "limit": 0.95, "asked": 8, "filled": 2,
     "extra": 4, "avgPrice": 0.95, "lag": 1.9, "result": "won"},
    {"ts": W1 + 483, "ticker": "KXSOL15M-1", "side": "yes", "seen": 0.96, "limit": 0.97, "asked": 12, "filled": 4,
     "extra": 5, "avgPrice": 0.968, "lag": 3.1, "result": "lost"},
    {"ts": W1 + 482, "ticker": "KXETH15M-1", "side": "no", "seen": 0.93, "limit": 0.94, "asked": 10, "filled": 10,
     "extra": 0, "avgPrice": None, "lag": 2.6, "result": "lost"},
    {"ts": W1 + 482, "ticker": "KXBTC15M-1", "side": "yes", "seen": 0.95, "limit": 0.96, "asked": 10, "filled": 6,
     "extra": 3, "avgPrice": 0.96, "lag": 2.4, "result": "won"},
    {"ts": WB + 482, "ticker": "KXETH15M-B", "side": "yes", "seen": 0.95, "limit": 0.96, "asked": 10, "filled": 10,
     "extra": 0, "avgPrice": None, "lag": 2.5, "result": "won"},
]
EMPTY_SHADOW = {"started": None, "until": UNTIL, "orders": 0, "unread": 0, "asked": 0, "filled": 0, "extra": 0,
                "fillShare": None, "fillShareWith": None, "remaining": 0, "extraShare": None, "ordersWithExtra": 0,
                "lag": None}


def shadow_of(mode="live-prod"):
    """The reply's shadow block, failing plainly if the reply has none."""
    r = dashboard.live_research(mode)
    assert "shadow" in r, f"no 'shadow' in the reply: {sorted(r)}"
    return r["shadow"]


def alike(got, want, path="shadow"):
    """Two replies' blocks are the same: dicts and lists item by item, numbers within 1e-9, everything else equal."""
    if isinstance(want, dict):
        assert isinstance(got, dict) and set(got) == set(want), f"{path}: keys {sorted(got)} vs {sorted(want)}"
        for k in want:
            alike(got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        assert isinstance(got, list) and len(got) == len(want), f"{path}: {got!r} vs {want!r}"
        for i, (g, w) in enumerate(zip(got, want)):
            alike(g, w, f"{path}[{i}]")
    elif isinstance(want, float) or isinstance(got, float):
        assert got is not None and want is not None and got == pytest.approx(want, abs=1e-9), f"{path}: {got!r} vs {want!r}"
    else:
        assert got == want, f"{path}: {got!r} vs {want!r}"


# ------------------------------------------------------------------ the reply
def test_the_reply_has_the_shadow_and_the_paper_cent(home, monkeypatch):
    """The paper card's cent is the bot's own constant, never a copy: both the reply's shadowUp and the block's limitUp."""
    measured(home).close()
    r = dashboard.live_research("live-prod")
    assert "shadow" in r and "shadowUp" in r, sorted(r)
    assert r["shadowUp"] == bot.SHADOW_UP and r["shadow"]["limitUp"] == bot.SHADOW_UP
    assert SHADOW_KEYS <= set(r["shadow"]) and GROUP_KEYS <= set(r["shadow"]["group"])
    assert {"state", "text", "orders", "until"} <= set(r["shadow"]["verdict"])
    assert "target" not in r["shadow"] and "target" not in r["shadow"]["verdict"]
    assert all(ROW_KEYS <= set(row) for row in r["shadow"]["rows"])
    json.dumps(r, allow_nan=False)                                         # plain JSON: no NaN or infinity
    monkeypatch.setattr(bot, "SHADOW_UP", 0.02)
    r = dashboard.live_research("live-prod")
    assert r["shadowUp"] == 0.02 and r["shadow"]["limitUp"] == 0.02


@pytest.mark.parametrize("fills", [True, False], ids=["fills-table-only", "neither-table"])
def test_without_a_shadow_table_the_shadow_is_null(home, fills):
    """A ledger from before the restart has no shadow table: the block is null, and the rest of the reply still works."""
    db = paper_ledger(home, shadow=False, fills=fills)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.95, 10, 10, bet=(W1, "won", 9.50, 0.05, 0.45))
    db.commit()
    db.close()
    r = dashboard.live_research("live-prod")
    assert "shadow" in r, sorted(r)
    assert r["shadow"] is None and r["shadowUp"] == bot.SHADOW_UP
    assert r["arms"]["before"]["orders"] == 1 and r["fillsRecorded"] is fills
    assert not [n for n in os.listdir(home.dir) if n.endswith(("-journal", "-wal", "-shm"))]


def test_an_empty_shadow_table_is_waiting(home):
    """The table is there but nothing was measured yet: every count 0, every share and the lag null."""
    paper_ledger(home).close()
    s = shadow_of()
    same(s, {"limitUp": bot.SHADOW_UP, **EMPTY_SHADOW})
    same(s["group"], EMPTY_GROUP)
    assert s["rows"] == []
    assert s["verdict"] == {"state": "waiting", "text": S_WAITING, "orders": 0, "until": UNTIL}


def test_the_route_serves_the_shadow(home):
    measured(home).close()
    with serving() as base:
        served = get(base, "/api/live-research")
    assert "shadow" in served, sorted(served)
    assert served["shadowUp"] == bot.SHADOW_UP
    assert served["shadow"] == json.loads(json.dumps(shadow_of(), default=str))   # the clock is frozen
    assert served["shadow"]["orders"] == 8


# ------------------------------------------------------------------ read only
def test_reading_the_shadow_never_changes_the_ledger(home):
    measured(home).close()
    path = home.dir / "live-prod.db"
    before, stamp, files = path.read_bytes(), os.stat(path).st_mtime_ns, sorted(os.listdir(home.dir))
    assert shadow_of()["orders"] == 8                                      # it did read the table
    assert path.read_bytes() == before and os.stat(path).st_mtime_ns == stamp
    assert sorted(os.listdir(home.dir)) == files                           # nothing new beside it
    assert not [n for n in os.listdir(home.dir) if n.endswith(("-journal", "-wal", "-shm"))]


def test_the_ledger_is_still_opened_read_only(home, monkeypatch):
    measured(home).close()
    real, calls = sqlite3.connect, []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", spy)
    assert shadow_of()["orders"] == 8
    assert calls, "live_research() never opened the ledger"
    for args, kwargs in calls:   # every connection, the shadow table's too: file:///.../live-prod.db?mode=ro, as a URI
        assert kwargs.get("uri") is True and str(args[0]).startswith("file:"), (args, kwargs)
        assert str(args[0]).endswith("live-prod.db?mode=ro"), (args, kwargs)


# ------------------------------------------------------------------ the counts and shares
def test_the_counts_and_fill_shares_by_hand(home):
    """The real fill share (contracts filled / asked for) against the share with the extra cent ((filled + extra) /
    asked), over the measured rows; and the share of the contracts the real orders left unfilled that the cent catches."""
    measured(home).close()
    same(shadow_of(), COUNTS)


def test_the_lag_is_the_median_of_the_measured_rows(home):
    """Even count: the mean of the middle two (2.4 and 2.5). The unread rows' lags (30 s, and none) are left out: with
    them it would be 2.5; the mean would be 2.4375."""
    measured(home).close()
    assert shadow_of()["lag"] == pytest.approx((2.4 + 2.5) / 2, abs=1e-9)


def test_the_lag_of_an_odd_number_of_rows_is_the_middle_one(home):
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 5, 1, 0.96, 0.0, lag=4.0)
    paper(db, W2 + 482, "KXBTC15M-2", W2, 0.95, 10, 5, 1, 0.96, 0.0, lag=1.0)
    paper(db, W3 + 482, "KXBTC15M-3", W3, 0.95, 10, 5, 1, 0.96, 0.0, lag=1.5)
    db.commit()
    assert shadow_of()["lag"] == pytest.approx(1.5, abs=1e-9)             # not the mean, 2.1667


def test_remaining_never_counts_a_row_below_zero(home):
    """remaining = Σ max(asked − filled, 0): should a market's bet ever top what its order asked for, that row adds
    nothing to the unfilled contracts rather than taking some away."""
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 12)
    paper(db, W1 + 483, "KXETH15M-1", W1, 0.95, 10, 4, 3, 3 * 0.96, 0.0)
    db.commit()
    s = shadow_of()
    same(s, {"asked": 20, "filled": 16, "extra": 3, "remaining": 6, "extraShare": 3 / 6, "fillShare": 16 / 20,
             "fillShareWith": 19 / 20})


# ------------------------------------------------------------------ the extra contracts
def test_the_extra_contracts_by_hand(home):
    """Each settled row's extra contracts: won, extra − cost − fee; lost, −cost − fee. Staked is what they cost."""
    measured(home).close()
    same(shadow_of()["group"], GROUP)
    assert shadow_of()["group"]["pnl"] == pytest.approx(-4.56) and shadow_of()["group"]["avgPrice"] == pytest.approx(20.86 / 22)


def test_the_standard_error_is_clustered_by_window(home):
    """Three settled windows, one with two rows: their residuals are summed in the window, then squared."""
    measured(home).close()
    assert clustered_se(WINDOWS) == pytest.approx(245.2606309513317, abs=1e-6)   # the hand arithmetic, checked once
    assert shadow_of()["group"]["se"] == pytest.approx(clustered_se(WINDOWS), abs=1e-9)


def test_rows_with_nothing_extra_count_in_the_shares_but_not_the_group(home):
    """An order that filled in full, or found no offer in the cent over the ask, still counts as measured: in the fill
    shares, the unfilled contracts and the verdict's count. It adds nothing to the extra contracts, not even a window."""
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 10, result="yes", lag=2.0)
    paper(db, W2 + 482, "KXBTC15M-2", W2, 0.95, 10, 4, result="no", lag=3.0)
    paper(db, W3 + 482, "KXBTC15M-3", W3, 0.95, 10, 10, lag=4.0)          # open
    db.commit()
    s = shadow_of()
    same(s, {"started": W1 + 482, "orders": 3, "unread": 0, "asked": 30, "filled": 24, "extra": 0, "fillShare": 24 / 30,
             "fillShareWith": 24 / 30, "remaining": 6, "extraShare": 0.0, "ordersWithExtra": 0, "lag": 3.0})
    same(s["group"], EMPTY_GROUP)
    assert [(row["ticker"], row["extra"], row["avgPrice"], row["result"]) for row in s["rows"]] == [
        ("KXBTC15M-3", 0, None, "open"), ("KXBTC15M-2", 0, None, "lost"), ("KXBTC15M-1", 0, None, "won")]
    assert s["verdict"]["orders"] == 3


def test_open_rows_count_in_contracts_price_and_fee_only(home):
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 6, 3, 3 * 0.96, 0.02, result="yes")
    paper(db, W2 + 482, "KXBTC15M-2", W2, 0.95, 10, 5, 2, 2 * 0.96, 0.01)  # open
    db.commit()
    same(shadow_of()["group"], {"orders": 2, "contracts": 5, "avgPrice": 0.96, "fee": 0.03, "breakEven": 0.96 + 0.03 / 5,
                                "settled": 3, "won": 3, "winRate": 1.0, "pnl": 3 * 0.04 - 0.02, "staked": 3 * 0.96,
                                "perTen": 1000 * (3 * 0.04 - 0.02) / (3 * 0.96), "se": None, "windows": 1})


def test_only_open_rows_have_no_win_rate_or_return(home):
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 6, 4, 4 * 0.96, 0.02)
    db.commit()
    same(shadow_of()["group"], {"orders": 1, "contracts": 4, "avgPrice": 0.96, "fee": 0.02, "breakEven": 0.96 + 0.02 / 4,
                                "settled": 0, "won": 0, "winRate": None, "pnl": 0, "staked": 0, "perTen": None,
                                "se": None, "windows": 0})


# ------------------------------------------------------------------ unread rows, and other experiments' rows
def test_unread_rows_count_only_as_unread(home):
    """A failed book read measured nothing: the same ledger without its two unread rows gives the same block, but
    for the unread count."""
    measured(home, unread=False, name="live-demo").close()
    measured(home).close()
    without, s = shadow_of("live-demo"), shadow_of()
    assert (s["unread"], without["unread"]) == (2, 0)
    alike({**s, "unread": 0}, without)
    assert "KXETH15M-2" not in [row["ticker"] for row in s["rows"]] and "KXDOGE15M-4" not in [row["ticker"] for row in s["rows"]]


def test_a_table_of_only_unread_rows(home, monkeypatch):
    """The bot has started recording (the first row's time) but every book read failed: nothing measured, so every
    count is 0 and every share null, and it is too early to tell rather than waiting for a restart."""
    ahead(monkeypatch)
    db = paper_ledger(home)
    paper(db, W1 + 482, "KXBTC15M-1", W1, 0.95, 10, 4, lag=None, unread=True)
    paper(db, W2 + 482, "KXBTC15M-2", W2, 0.95, 10, 10, lag=12.0, unread=True)
    db.commit()
    s = shadow_of()
    same(s, {**EMPTY_SHADOW, "started": W1 + 482, "unread": 2, "until": dashboard.SHADOW_UNTIL})
    same(s["group"], EMPTY_GROUP)
    assert s["rows"] == []
    assert s["verdict"] == {"state": "too-early", "text": S_TOO_EARLY.format(n=0), "orders": 0,
                            "until": dashboard.SHADOW_UNTIL}


def fast_rows(db):
    """Rows another paper experiment ("fast entry", kind 'fast') writes to the same table: one in a market the +1c rows
    have too, one older than all of them, one newer, one in a window of its own, and an unread one."""
    paper(db, W1 + 470, "KXBTC15M-1", W1, 0.93, 10, 6, 9, 9 * 0.93, 0.05, result="yes", lag=0.3, kind="fast")
    paper(db, WA + 470, "KXBTC15M-A", WA, 0.92, 10, 0, 10, 9.30, 0.05, result="no", lag=0.4, kind="fast")
    paper(db, W4 + 499, "KXHYPE15M-4", W4, 0.91, 10, 0, 8, 8 * 0.91, 0.04, lag=0.5, kind="fast")
    paper(db, W3 + 470, "KXSOL15M-3", W3, 0.94, 10, 2, 7, 7 * 0.94, 0.03, side="no", result="yes", lag=0.2, kind="fast")
    paper(db, W2 + 470, "KXETH15M-2", W2, 0.92, 10, 3, lag=0.6, unread=True, kind="fast")


def test_another_kinds_rows_are_ignored(home):
    """The shadow block reads only kind 'limitup': another experiment's rows, even in the same market, change no number,
    neither the start, the counts, the lag, the extra contracts, the verdict nor the rows listed."""
    measured(home, name="live-demo").close()
    measured(home, also=fast_rows).close()
    with_fast, without = shadow_of(), shadow_of("live-demo")
    alike(with_fast, without)
    same(with_fast, COUNTS)
    assert [row["ticker"] for row in with_fast["rows"]] == [row["ticker"] for row in ROWS]


def test_only_another_kinds_rows_is_still_waiting(home):
    db = paper_ledger(home)
    fast_rows(db)
    db.commit()
    s = shadow_of()
    same(s, EMPTY_SHADOW)
    same(s["group"], EMPTY_GROUP)
    assert s["rows"] == []
    assert s["verdict"] == {"state": "waiting", "text": S_WAITING, "orders": 0, "until": UNTIL}


# ------------------------------------------------------------------ the rows listed
def test_the_rows_newest_first_with_every_field(home):
    """Each measured row: the ask it saw, the paper limit, the real order's asked and filled, the extra contracts and
    their average price (null with none), the lag, and how it ended: won or lost (its side against the market's
    result, even with nothing extra), or open."""
    measured(home).close()
    rows = shadow_of()["rows"]
    assert [row["ticker"] for row in rows] == [row["ticker"] for row in ROWS]
    for got, want in zip(rows, ROWS):
        assert ROW_KEYS <= set(got), got
        same(got, want)


def test_at_most_50_rows_are_listed(home):
    db = paper_ledger(home)
    for i in range(55):
        ts = NOW - 50000 + 900 * i
        paper(db, ts, f"KXETH15M-{i:02d}", ts - 482, 0.95, 10, 5, 1, 0.96, 0.0)
        if i % 10 == 9:   # a failed read just after it: never listed
            paper(db, ts + 1, f"KXSOL15M-{i:02d}", ts - 482, 0.95, 10, 5, unread=True)
    db.commit()
    s = shadow_of()
    assert [row["ticker"] for row in s["rows"]] == [f"KXETH15M-{i:02d}" for i in range(54, 4, -1)]
    assert s["orders"] == 55 and s["unread"] == 5                          # the counts still have every row


# ------------------------------------------------------------------ the paper verdict
def paid(db, ts, ticker, window, extra, result, seen=0.95, side="yes"):
    """A measured row whose `extra` contracts were all a cent over the ask it saw, without fees."""
    over = round(seen + 0.01, 4)
    paper(db, ts, ticker, window, seen, 10, 10 - extra, extra, extra * over, 0.0, side=side, result=result)


def test_shadow_too_early_before_the_date(home, monkeypatch):
    measured(home).close()
    assert dashboard.SHADOW_UNTIL == UNTIL
    ahead(monkeypatch)
    v = shadow_of()["verdict"]
    assert v == {"state": "too-early", "text": S_TOO_EARLY.format(n=8), "orders": 8, "until": dashboard.SHADOW_UNTIL}
    assert v["text"] == "Too early to tell: 8 orders measured on paper so far. The verdict comes on Nov 27, after 6 weeks."


def test_shadow_too_early_counts_only_the_measured_orders(home, monkeypatch):
    """Ten rows, but the two unread ones don't count as measured."""
    measured(home).close()
    ahead(monkeypatch)
    s = shadow_of()
    assert s["until"] == dashboard.SHADOW_UNTIL
    assert s["verdict"] == {"state": "too-early", "text": S_TOO_EARLY.format(n=8), "orders": 8,
                            "until": dashboard.SHADOW_UNTIL}


def test_shadow_thin_without_a_standard_error(home, monkeypatch):
    """After the date, extra contracts settled in only one window: no standard error, so no range to read."""
    db = paper_ledger(home)
    paid(db, W1 + 482, "KXBTC15M-1", W1, 5, "yes")
    paid(db, W1 + 483, "KXETH15M-1", W1, 5, "no")
    paid(db, W2 + 482, "KXBTC15M-2", W2, 5, None)                          # open: one settled window, no standard error
    db.commit()
    past(monkeypatch)
    s = shadow_of()
    assert s["group"]["se"] is None and s["group"]["perTen"] is not None
    assert s["verdict"] == {"state": "thin", "text": S_THIN.format(n=3), "orders": 3, "until": dashboard.SHADOW_UNTIL}


def test_shadow_no_difference_when_the_range_includes_zero(home, monkeypatch):
    measured(home).close()
    past(monkeypatch)                                                      # the date has come: the range decides
    s = shadow_of()
    g = s["group"]
    assert g["perTen"] - 1.96 * g["se"] < 0 < g["perTen"] + 1.96 * g["se"]   # about −819 to +142 ¢ per $10
    assert s["verdict"] == {"state": "no-difference", "text": S_NO_DIFFERENCE, "orders": 8, "until": dashboard.SHADOW_UNTIL}


def test_shadow_helping_when_the_whole_range_is_above_zero(home, monkeypatch):
    db = paper_ledger(home)
    paid(db, W1 + 482, "KXBTC15M-1", W1, 5, "yes")
    paid(db, W2 + 482, "KXBTC15M-2", W2, 5, "yes")
    paid(db, W3 + 482, "KXBTC15M-3", W3, 4, "no", seen=0.96, side="no")
    db.commit()
    past(monkeypatch)
    s = shadow_of()
    windows = [(5 * 0.04, 5 * 0.96), (5 * 0.04, 5 * 0.96), (4 * 0.03, 4 * 0.97)]
    g = s["group"]
    assert g["perTen"] == pytest.approx(1000 * 0.52 / 13.48) and g["se"] == pytest.approx(clustered_se(windows), abs=1e-9)
    assert g["perTen"] - 1.96 * g["se"] > 0                                 # about +38.6 ± 6.5
    assert s["verdict"] == {"state": "helping", "text": S_HELPING, "orders": 3, "until": dashboard.SHADOW_UNTIL}


def test_shadow_hurting_when_the_whole_range_is_below_zero(home, monkeypatch):
    db = paper_ledger(home)
    paid(db, W1 + 482, "KXBTC15M-1", W1, 5, "no")
    paid(db, W1 + 483, "KXETH15M-1", W1, 0, "yes")                         # nothing extra: counts as an order only
    paid(db, W2 + 482, "KXBTC15M-2", W2, 5, "no")
    paid(db, W3 + 482, "KXBTC15M-3", W3, 5, "no")
    paid(db, W4 + 482, "KXBTC15M-4", W4, 5, "yes")
    db.commit()
    past(monkeypatch)
    s = shadow_of()
    windows = [(-4.8, 4.8), (-4.8, 4.8), (-4.8, 4.8), (5 * 0.04, 4.8)]
    g = s["group"]
    assert g["perTen"] == pytest.approx(1000 * -14.2 / 19.2) and g["se"] == pytest.approx(clustered_se(windows), abs=1e-9)
    assert g["perTen"] + 1.96 * g["se"] < 0                                 # about −740 ± 510
    assert s["verdict"] == {"state": "hurting", "text": S_HURTING, "orders": 5, "until": dashboard.SHADOW_UNTIL}


# ------------------------------------------------------------------ the live card: off while the live limit is at the ask
@pytest.mark.parametrize("up", [0.0, 0], ids=["0.0", "0"])
def test_the_live_card_is_off_while_real_orders_go_at_the_ask(home, monkeypatch, up):
    """With bot.LIMIT_UP at 0 and no order ever over the ask it saw, there is no live experiment to wait for: it's off.
    The orders it did send are all in the before arm."""
    monkeypatch.setattr(bot, "LIMIT_UP", up)
    db = paper_ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.95, 10, 10, bet=(W1, "won", 9.50, 0.05, 0.45))
    trade(db, W2 + 480, "KXETH15M-2", 0.93, 0.93, 10, 0)
    paper(db, W1 + 480, "KXBTC15M-1", W1, 0.95, 10, 10)
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] is None and r["limitUp"] == up
    assert r["verdict"] == {"state": "off", "text": OFF, "orders": 0, "target": 1000}
    assert r["arms"]["before"]["orders"] == 2 and r["arms"]["during"]["orders"] == 0


def test_an_empty_ledger_is_off_too(home, monkeypatch):
    monkeypatch.setattr(bot, "LIMIT_UP", 0.0)
    paper_ledger(home, shadow=False).close()
    assert dashboard.live_research("live-prod")["verdict"] == {"state": "off", "text": OFF, "orders": 0, "target": 1000}


def test_with_a_live_cent_and_nothing_started_it_is_waiting(home, monkeypatch):
    monkeypatch.setattr(bot, "LIMIT_UP", 0.01)
    db = paper_ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.95, 10, 10, bet=(W1, "won", 9.50, 0.05, 0.45))
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] is None
    assert r["verdict"] == {"state": "waiting", "text": WAITING, "orders": 0, "target": 1000}


def test_off_only_while_no_order_had_the_live_cent(home, monkeypatch):
    """Once a real +1c order is in the ledger (the live limit was on for a while), the live card follows it as before,
    whatever bot.LIMIT_UP is now."""
    monkeypatch.setattr(bot, "LIMIT_UP", 0.0)
    db = paper_ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.03), (4, 0.96, 0.02)],
          bet=(W1, "won", 9.54, 0.05, 0.41))
    trade(db, W2 + 480, "KXETH15M-2", 0.93, 0.93, 10, 0)                  # at the ask again: still a during order
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] == W1 + 480
    assert r["verdict"] == {"state": "too-early", "text": "Too early to tell: 2 of 1000 orders with the +1¢ limit so far.",
                            "orders": 2, "target": 1000}


# ------------------------------------------------------------------ the limits
def test_the_limits_carry_the_paper_cent(home, monkeypatch):
    """The page's "How it trades" says what the bot measures on paper: read from the bot, never a copy."""
    paper_ledger(home).close()
    lim = dashboard.state("live-prod")["limits"]
    assert "shadowUp" in lim, sorted(lim)
    assert lim["shadowUp"] == bot.SHADOW_UP and lim["limitUp"] == bot.LIMIT_UP
    monkeypatch.setattr(bot, "SHADOW_UP", 0.02)
    assert dashboard.state("live-prod")["limits"]["shadowUp"] == 0.02
