"""Fast entry on paper, in the Live Research tab's server side (GET /api/live-research). The bot's real minute-8 orders
land a median 2.4 s after minute 8 starts, by when other traders have taken much of the volume at its limit. In the
background the bot reads every order book at minute 8 exactly (480.0 s into the window on Kalshi's clock, "the mark")
and pairs each real order with a paper twin: what an order sent at that instant, with the same limit rule, would have
bought in the mark's book. Each pair is a row of the ledger's shadow table with kind 'fast' (the paper +1¢ shares the
table with kind 'limitup'). Paper means no money moves: the twin's contracts are only counted, then settled with the
market like a bet.

live_research() reads those rows into a "fastShadow" block: how many orders were paired and how many books couldn't be
read ("unread"), the real fill share (contracts filled / asked for) against the share at the mark, their difference with
a standard error clustered by window (orders in one 15-minute window share their luck, so the window is the unit), the
share of the real orders' misses the mark's book had ("caught"), the asks each saw and the prices each paid, how long
after minute 8 the mark's book answered ("lag": its median and 90th percentile), the P&L of the settled pairs on paper
and for real, a verdict once FAST_SHADOW_TARGET orders are paired, and the latest pairs. With no shadow table (a ledger
from before the restart) the block is null. Nothing else in the reply changes.

Every ledger here is built with explicit CREATE TABLE statements (test_shadow_api.py's), not bot.connect(), so they stay
the same when bot.connect() changes. Each number is worked out by hand in the test. The ledger is opened read-only and
never changed. Nothing here touches the network or the real research files.

    python -m pytest tests/test_fast_shadow_api.py -q
"""
import json
import math
import os

import pytest

from kalshi_bot.web import dashboard
from kalshi_bot import fast_entry
from test_dashboard_more import NOW, home, serving  # noqa: F401  (home is a fixture)
from test_live_research_api import W1, W2, W3, W4, clustered_se, get, same
from test_shadow_api import COUNTS, measured, paper_ledger
from test_shadow_api import ROWS as LIMITUP_ROWS

# The card's verdicts, word for word
F_WAITING = "Not recording yet: the bot reads the order books at minute 8 exactly from its next restart."
F_TOO_EARLY = "Too early to tell: {n} of {target} orders paired on paper so far."
F_MORE = "Orders sent at minute 8 exactly would fill more: the difference's 95% range is above zero."
F_LESS = "Orders sent at minute 8 exactly would fill less: the difference's 95% range is below zero."
F_NO_DIFFERENCE = "No clear difference in fills: the difference's 95% range includes zero."

BLOCK_KEYS = {"started", "target", "orders", "unread", "asked", "filled", "extra", "realShare", "fastShare", "diff",
              "diffSe", "caught", "realSeen", "fastSeen", "realAvg", "fastAvg", "lag", "pnl", "verdict", "rows"}
ROW_KEYS = {"ts", "ticker", "side", "seenReal", "seen", "limit", "asked", "filled", "extra", "avgPrice", "lag", "pnl",
            "result"}
RETURNS_KEYS = {"pnl", "staked", "perTen", "se"}
VERDICT_KEYS = {"state", "text", "orders", "target"}
NOTHING = {"pnl": 0, "staked": 0, "perTen": None, "se": None}            # returns() of nothing settled


@pytest.fixture(autouse=True)
def no_real_research(tmp_path_factory, monkeypatch):
    """No test reads the real research folder (the reply's predictions come from it): each gets an empty one."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path_factory.mktemp("research")))


# ------------------------------------------------------------------ building a ledger
def fast(db, ts, ticker, window, asked, filled, extra=0.0, cost=0.0, fee=0.0, seen=0.95, side="yes", result=None,
         lag=0.05, unread=False, out_of_band=False):
    """One paired order as the bot writes it and settles it: the real order asked for `asked` contracts and its bet got
    `filled`; at the mark an order with the same limit rule would have bought `extra` for `cost`, plus `fee`, from a
    book whose ask on its side was `seen` (None: nobody selling on that side) and that answered `lag` seconds after
    minute 8. The paper limit is the ask itself (bot.LIMIT_UP is 0), or none when the ask was outside the strategy's band
    (out_of_band: it would not have bought, so nothing extra). result: the market's result ("yes"/"no") once settled,
    None while open. unread: the book couldn't be read or parsed, so nothing was measured (seen, limit, extra, cost and
    fee are NULL; the lag is kept if the book answered). A settled row's P&L: its contracts pay $1 each if its side won,
    less what they cost and their fee."""
    status = "unread" if unread else "open" if result is None else "settled"
    if unread:
        seen = extra = cost = fee = None
    limit = None if unread or out_of_band or seen is None else seen
    pnl = (extra if side == result else 0) - cost - fee if status == "settled" else None
    db.execute("INSERT INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price, asked, filled,"
               " lag, extra, cost, fee, status, result, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("fast", ticker, ts, window, window + 900, ticker.split("-")[0], side, seen, limit, asked, filled, lag,
                extra, cost, fee, status, result if status == "settled" else None, pnl,
                window + 960 if status == "settled" else None))


def decision(db, ts, ticker, fav_price, side="yes"):
    """The bot's decision on a market, with the ask it saw on the favourite's side (fav_price; None: not recorded)."""
    db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
               (ts, ticker, ticker.split("-")[0], side, fav_price, "bet", "test"))


def bet(db, ticker, window, contracts, cost, status="open", pnl=None, side="yes"):
    """The real bet a market's order made: its contracts and what they cost; won or lost with its P&L, or open."""
    settled = status in ("won", "lost")
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts,"
               " status, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, ticker.split("-")[0], window, window + 900, side, cost / contracts if contracts else None,
                contracts, cost, 0.0, window + 482, status, pnl if settled else None, window + 960 if settled else None))


def paired_rows(db):
    """Eight paired orders over four windows, as the bot writes them (not in time order: the unread one at W1 + 481
    was written third). Six were measured: two won and one lost on paper; one settled having bought nothing (no offers
    on its side at the mark); one is open with nothing bought (the mark's ask under the band) and a NULL lag; one is
    open. Two books couldn't be read (unread), one of them the earliest row of all."""
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 6, 10, 10 * 0.94, 0.04, seen=0.94, result="yes", lag=0.05)        # won
    fast(db, W1 + 482, "KXETH15M-1", W1, 10, 10, 8, 8 * 0.93, 0.04, seen=0.93, side="no", result="yes", lag=0.12)  # lost
    fast(db, W1 + 481, "KXDOGE15M-1", W1, 10, 3, lag=0.5, unread=True)                         # the first row: unread
    fast(db, W2 + 482, "KXSOL15M-2", W2, 12, 4, 12, 12 * 0.96, 0.05, seen=0.96, result="yes", lag=0.30)       # won
    fast(db, W3 + 482, "KXXRP15M-3", W3, 10, 0, seen=None, result="no", lag=0.08)        # nothing on its side; lost
    fast(db, W3 + 483, "KXBTC15M-3", W3, 8, 2, seen=0.88, side="no", lag=None, out_of_band=True)                # open
    fast(db, W3 + 484, "KXSOL15M-3", W3, 10, 0, side="no", lag=None, unread=True)
    fast(db, W4 + 482, "KXETH15M-4", W4, 10, 0, 6, 6 * 0.95, 0.02, seen=0.95, lag=0.20)                         # open


def real_orders(db):
    """What the real orders of paired_rows saw and bought: the decisions (one market has none, one a NULL price) and
    the bets (one market got nothing, so no bet; one bet has no contracts; the unread market's bet doesn't count)."""
    decision(db, W1 + 480, "KXBTC15M-1", 0.95)
    bet(db, "KXBTC15M-1", W1, 6, 5.70, "won", 0.27)
    decision(db, W1 + 480, "KXETH15M-1", 0.93, side="no")
    bet(db, "KXETH15M-1", W1, 10, 9.30, "lost", -9.35, side="no")
    decision(db, W1 + 480, "KXDOGE15M-1", 0.90)                          # unread: neither counts
    bet(db, "KXDOGE15M-1", W1, 3, 2.70, "won", 0.27)
    bet(db, "KXSOL15M-2", W2, 4, 3.84, "won", 0.14)                      # no decision row
    decision(db, W3 + 480, "KXXRP15M-3", 0.92)                           # got nothing: no bet
    decision(db, W3 + 480, "KXBTC15M-3", None, side="no")                # its price wasn't recorded
    bet(db, "KXBTC15M-3", W3, 2, 1.90, "open", side="no")
    decision(db, W4 + 480, "KXETH15M-4", 0.95)
    bet(db, "KXETH15M-4", W4, 0, 0.0, "open")                            # a bet of no contracts


def paired(home, name="live-prod"):
    """A ledger with paired_rows and their real orders, committed."""
    db = paper_ledger(home, name=name)
    paired_rows(db)
    real_orders(db)
    db.commit()
    return db


def both(db):
    """paired_rows and their real orders, for measured(also=...) to add among the paper +1¢'s rows."""
    paired_rows(db)
    real_orders(db)


# Its numbers by hand. Measured rows: all but the two unread ones (KXDOGE15M-1, KXSOL15M-3).
MAIN = {"started": W1 + 481, "target": 300, "orders": 6, "unread": 2,
        "asked": 10 + 10 + 12 + 10 + 8 + 10, "filled": 6 + 10 + 4 + 0 + 2 + 0, "extra": 10 + 8 + 12 + 0 + 0 + 6,
        "realShare": 22 / 60, "fastShare": 36 / 60, "diff": 36 / 60 - 22 / 60,
        # Σmax(extra − filled, 0) / Σmax(asked − filled, 0): 4 + 0 + 8 + 0 + 0 + 6 over 4 + 0 + 8 + 10 + 6 + 10
        "caught": 18 / 38,
        "realSeen": (0.95 + 0.93 + 0.92 + 0.95) / 4,                        # no decision for SOL-2, NULL for BTC-3
        "fastSeen": (0.94 + 0.93 + 0.96 + 0.88 + 0.95) / 5,                 # nothing on XRP-3's side: no ask
        "realAvg": (5.70 + 9.30 + 3.84 + 1.90) / (6 + 10 + 4 + 2),          # 20.74 / 22; ETH-4's bet has no contracts
        "fastAvg": (9.40 + 7.44 + 11.52 + 5.70) / 36}                       # 34.06 / 36
# Each window's (Σ(extra − filled), Σasked) over its measured rows: W1 (BTC-1, ETH-1), W2, W3 (XRP-3, BTC-3), W4
WINDOW_SUMS = [(4 - 2, 10 + 10), (8, 12), (0 - 2, 10 + 8), (6, 10)]
# Each settled window's (P&L, staked) on paper, over the settled rows that cost something: W1 (one won, one lost) and
# W2. XRP-3 settled in W3 having bought nothing: no window of its own.
PAPER_WINDOWS = [((10 - 9.40 - 0.04) + (-7.44 - 0.04), 9.40 + 7.44), (12 - 11.52 - 0.05, 11.52)]
# ... and for real, the won or lost bets of those settled rows' markets (XRP-3 got no bet)
REAL_WINDOWS = [(0.27 - 9.35, 5.70 + 9.30), (0.14, 3.84)]
# The measured rows, newest first (two at the same moment: the one written later first)
MAIN_ROWS = [
    {"ts": W4 + 482, "ticker": "KXETH15M-4", "side": "yes", "seenReal": 0.95, "seen": 0.95, "limit": 0.95, "asked": 10,
     "filled": 0, "extra": 6, "avgPrice": 0.95, "lag": 0.20, "pnl": None, "result": "open"},
    {"ts": W3 + 483, "ticker": "KXBTC15M-3", "side": "no", "seenReal": None, "seen": 0.88, "limit": None, "asked": 8,
     "filled": 2, "extra": 0, "avgPrice": None, "lag": None, "pnl": None, "result": "open"},
    {"ts": W3 + 482, "ticker": "KXXRP15M-3", "side": "yes", "seenReal": 0.92, "seen": None, "limit": None, "asked": 10,
     "filled": 0, "extra": 0, "avgPrice": None, "lag": 0.08, "pnl": 0, "result": "lost"},
    {"ts": W2 + 482, "ticker": "KXSOL15M-2", "side": "yes", "seenReal": None, "seen": 0.96, "limit": 0.96, "asked": 12,
     "filled": 4, "extra": 12, "avgPrice": 0.96, "lag": 0.30, "pnl": 12 - 11.52 - 0.05, "result": "won"},
    {"ts": W1 + 482, "ticker": "KXETH15M-1", "side": "no", "seenReal": 0.93, "seen": 0.93, "limit": 0.93, "asked": 10,
     "filled": 10, "extra": 8, "avgPrice": 0.93, "lag": 0.12, "pnl": -7.44 - 0.04, "result": "lost"},
    {"ts": W1 + 482, "ticker": "KXBTC15M-1", "side": "yes", "seenReal": 0.95, "seen": 0.94, "limit": 0.94, "asked": 10,
     "filled": 6, "extra": 10, "avgPrice": 0.94, "lag": 0.05, "pnl": 10 - 9.40 - 0.04, "result": "won"},
]
EMPTY = {"started": None, "target": 300, "orders": 0, "unread": 0, "asked": 0, "filled": 0, "extra": 0,
         "realShare": None, "fastShare": None, "diff": None, "diffSe": None, "caught": None, "realSeen": None,
         "fastSeen": None, "realAvg": None, "fastAvg": None, "lag": {"median": None, "p90": None},
         "pnl": {"settled": 0, "paper": NOTHING, "real": NOTHING},
         "verdict": {"state": "waiting", "text": F_WAITING, "orders": 0, "target": 300}, "rows": []}


def ratio_se_by_hand(sums):
    """The difference's standard error, clustered by window, from each window's (nⱼ, dⱼ) = (Σ(extra − filled), Σasked):
    with R = Σn / Σd and J windows, √(J/(J−1) · Σ(nⱼ − R·dⱼ)²) / Σd."""
    n, d, j = sum(a for a, _ in sums), sum(b for _, b in sums), len(sums)
    r = n / d
    return math.sqrt(j / (j - 1) * sum((a - r * b) ** 2 for a, b in sums)) / d


def fast_of(mode="live-prod"):
    """The reply's fastShadow block, failing plainly if the reply has none."""
    r = dashboard.live_research(mode)
    assert "fastShadow" in r, f"no 'fastShadow' in the reply: {sorted(r)}"
    return r["fastShadow"]


def alike(got, want, path="fastShadow"):
    """Two blocks are the same: dicts with the same keys and lists item by item, numbers within 1e-9, None still None,
    everything else equal."""
    if isinstance(want, dict):
        assert isinstance(got, dict) and set(got) == set(want), f"{path}: keys {sorted(got)} vs {sorted(want)}"
        for k in want:
            alike(got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        assert isinstance(got, list) and len(got) == len(want), f"{path}: {got!r} vs {want!r}"
        for i, (g, w) in enumerate(zip(got, want)):
            alike(g, w, f"{path}[{i}]")
    elif isinstance(want, (int, float)) and not isinstance(want, bool):
        assert isinstance(got, (int, float)) and not isinstance(got, bool), f"{path}: {got!r} vs {want!r}"
        assert got == pytest.approx(want, abs=1e-9), f"{path}: {got!r} vs {want!r}"
    else:
        assert got == want, f"{path}: {got!r} vs {want!r}"


# ------------------------------------------------------------------ the reply
def test_the_target_is_300_paired_orders():
    """About two days at ~140 orders a day before the card gives a verdict."""
    assert dashboard.FAST_SHADOW_TARGET == 300


@pytest.mark.parametrize("fills", [True, False], ids=["fills-table-only", "neither-table"])
def test_without_a_shadow_table_fast_shadow_is_null(home, fills):
    """A ledger from before the restart has no shadow table: both paper blocks are null, and the reply is plain JSON."""
    db = paper_ledger(home, shadow=False, fills=fills)
    real_orders(db)
    db.commit()
    db.close()
    r = dashboard.live_research("live-prod")
    assert "fastShadow" in r, sorted(r)
    assert r["fastShadow"] is None and r["shadow"] is None
    json.dumps(r, allow_nan=False)
    assert not [n for n in os.listdir(home.dir) if n.endswith(("-journal", "-wal", "-shm"))]


def test_an_empty_shadow_table_is_waiting(home):
    """The table is there but nothing was paired yet: every count and sum 0, every ratio, average and lag null, nothing
    settled, no rows, and it waits for the bot's next restart."""
    paper_ledger(home).close()
    r = dashboard.live_research("live-prod")
    alike(r["fastShadow"], EMPTY)
    assert r["fastShadow"]["verdict"]["text"] == F_WAITING
    json.dumps(r, allow_nan=False)


def test_the_block_has_exactly_the_specs_keys(home):
    paired(home).close()
    f = fast_of()
    assert set(f) == BLOCK_KEYS
    assert set(f["lag"]) == {"median", "p90"} and set(f["pnl"]) == {"settled", "paper", "real"}
    assert set(f["pnl"]["paper"]) == RETURNS_KEYS and set(f["pnl"]["real"]) == RETURNS_KEYS
    assert set(f["verdict"]) == VERDICT_KEYS
    assert f["rows"] and all(set(row) == ROW_KEYS for row in f["rows"])


# ------------------------------------------------------------------ kept apart from the paper +1¢
def test_only_limitup_rows_is_still_waiting(home):
    """The paper +1¢'s rows (kind 'limitup') are another experiment's: with only those the fast block is empty."""
    measured(home).close()
    r = dashboard.live_research("live-prod")
    assert r["shadow"]["orders"] == 8                                      # the +1¢ rows are there
    alike(r["fastShadow"], EMPTY)


def test_limitup_rows_never_leak_into_fast_shadow(home):
    """The same paired orders with and without the paper +1¢'s rows (some in the same markets, one written before all
    of them): the fast block is the same, number for number and row for row."""
    paired(home, name="live-demo").close()
    measured(home, also=both).close()
    with_limitup, without = fast_of(), fast_of("live-demo")
    alike(with_limitup, without)
    same(with_limitup, MAIN)
    assert [row["ticker"] for row in with_limitup["rows"]] == [row["ticker"] for row in MAIN_ROWS]


def test_fast_rows_never_leak_into_the_limitup_shadow(home):
    """The +1¢ block reads only kind 'limitup': the fast rows change none of its numbers or rows."""
    measured(home, name="live-demo").close()
    measured(home, also=both).close()
    with_fast, without = dashboard.live_research("live-prod")["shadow"], dashboard.live_research("live-demo")["shadow"]
    same(with_fast, COUNTS)
    assert (with_fast["orders"], with_fast["asked"]) == (8, 80)
    assert with_fast == without
    assert [row["ticker"] for row in with_fast["rows"]] == [row["ticker"] for row in LIMITUP_ROWS]


def test_nothing_else_in_the_reply_changes(home):
    """The fast rows add the fastShadow block and nothing else: the rest of the reply is the same without them."""
    db = paper_ledger(home, name="live-demo")
    real_orders(db)
    db.commit()
    db.close()
    paired(home).close()
    with_fast, without = dashboard.live_research("live-prod"), dashboard.live_research("live-demo")
    assert with_fast["fastShadow"]["orders"] == 6 and without["fastShadow"]["orders"] == 0
    drop = lambda r: {k: v for k, v in r.items() if k not in ("mode", "fastShadow")}
    assert drop(with_fast) == drop(without)


# ------------------------------------------------------------------ the counts, sums and shares
def test_started_is_the_first_rows_time_even_unread(home):
    """The first row by time (then by id) starts it, though its book couldn't be read and it was written third."""
    paired(home).close()
    f = fast_of()
    assert f["started"] == pytest.approx(W1 + 481, abs=1e-9)
    assert (f["orders"], f["unread"], f["target"]) == (6, 2, 300)


def test_the_sums_are_over_measured_rows_only(home):
    """The unread rows (asked 10 and 10, the first with 3 filled for real) add nothing to asked, filled or extra."""
    paired(home).close()
    same(fast_of(), {"asked": 60, "filled": 22, "extra": 36})


def test_the_fill_shares_and_their_difference(home):
    """Real fill share = filled / asked; at the mark = extra / asked; the difference = the mark's share − the real one."""
    paired(home).close()
    f = fast_of()
    same(f, {"realShare": 22 / 60, "fastShare": 0.6, "diff": 14 / 60})
    assert f["diff"] == pytest.approx(f["fastShare"] - f["realShare"], abs=1e-12)


def test_the_differences_standard_error_by_hand(home):
    """Clustered by window: each window's Σ(extra − filled) and Σasked are summed first, then the residuals from the
    overall ratio are squared. Four windows: √(4/3 · Σ(nⱼ − 14/60·dⱼ)²) / 60 ≈ 0.1785."""
    paired(home).close()
    by_hand = ratio_se_by_hand(WINDOW_SUMS)
    assert by_hand == pytest.approx(0.1785077605487551, abs=1e-9)          # the hand arithmetic, checked once
    rows = [(W1, 10 - 6, 10), (W1, 8 - 10, 10), (W2, 12 - 4, 12), (W3, 0 - 0, 10), (W3, 0 - 2, 8), (W4, 6 - 0, 10)]
    r, se = fast_entry.ratio_se(fast_entry.by_window(rows))
    assert r == pytest.approx(14 / 60) and se == pytest.approx(by_hand, abs=1e-12)
    assert fast_of()["diffSe"] == pytest.approx(by_hand, abs=1e-9)


def test_one_window_has_no_standard_error(home):
    """Two orders in one window are one draw: the difference is there, its standard error isn't."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, 8, 8 * 0.95, 0.03)
    fast(db, W1 + 483, "KXETH15M-1", W1, 10, 6, 7, 7 * 0.95, 0.03)
    db.commit()
    f = fast_of()
    same(f, {"realShare": 0.5, "fastShare": 0.75, "diff": 0.25, "diffSe": None})


def test_caught_is_the_share_of_real_misses_the_mark_had(home):
    """Σmax(extra − filled, 0) / Σmax(asked − filled, 0): an order whose twin bought fewer than it did (8 < 10, 0 < 2)
    adds nothing, rather than taking some away."""
    paired(home).close()
    assert fast_of()["caught"] == pytest.approx(18 / 38, abs=1e-9)


def test_caught_never_counts_a_row_below_zero(home):
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, 7, 7 * 0.95, 0.03)       # 3 of its 6 misses
    fast(db, W2 + 482, "KXETH15M-2", W2, 10, 8, 2, 2 * 0.95, 0.01)       # fewer at the mark: 0, not −6
    db.commit()
    assert fast_of()["caught"] == pytest.approx(3 / (6 + 2), abs=1e-9)    # unclamped it'd be −3/8


def test_caught_is_null_when_every_order_filled(home):
    """No real misses to catch: null, not a division by zero."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 10, 10, 10 * 0.95, 0.03)
    fast(db, W2 + 482, "KXETH15M-2", W2, 5, 5, 3, 3 * 0.95, 0.01)
    db.commit()
    f = fast_of()
    same(f, {"caught": None, "realShare": 1.0, "fastShare": 13 / 15, "diff": 13 / 15 - 1})


# ------------------------------------------------------------------ the asks and the prices
def test_the_asks_seen_real_and_at_the_mark(home):
    """Real: the decisions' price over the measured rows that have one (none for SOL-2, NULL for BTC-3; the unread
    DOGE-1's 0.90 left out). At the mark: the rows' non-null asks (XRP-3 had nobody selling on its side)."""
    paired(home).close()
    same(fast_of(), {"realSeen": 0.9375, "fastSeen": 0.932})


def test_the_prices_paid_real_and_at_the_mark(home):
    """Real: Σcost / Σcontracts over the measured rows' bets with contracts (XRP-3 has no bet, ETH-4's has none; the
    unread DOGE-1's is left out: with it 23.44 / 25). At the mark: Σcost / Σextra."""
    paired(home).close()
    f = fast_of()
    same(f, {"realAvg": 20.74 / 22, "fastAvg": 34.06 / 36})


def test_nothing_bought_at_the_mark(home):
    """No offers on its side for one, the ask under the band for the other: the mark's share is 0, its average price
    null (not a division by zero), its average ask the one it did see, and it caught none of the misses."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, seen=None)
    fast(db, W2 + 482, "KXETH15M-2", W2, 10, 10, seen=0.85, out_of_band=True)
    db.commit()
    f = fast_of()
    same(f, {"orders": 2, "extra": 0, "realShare": 0.7, "fastShare": 0.0, "diff": -0.7, "caught": 0.0, "fastSeen": 0.85,
             "fastAvg": None})
    assert [(row["seen"], row["limit"], row["avgPrice"]) for row in f["rows"]] == [(0.85, None, None), (None, None, None)]


def test_without_decisions_or_bets_the_real_side_is_null(home):
    """Rows whose markets have no decision and no bet: no real ask or price, no real P&L, and each row's seenReal null."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, 8, 8 * 0.95, 0.03, result="yes")
    fast(db, W2 + 482, "KXETH15M-2", W2, 10, 6, 7, 7 * 0.95, 0.03, result="no")
    db.commit()
    f = fast_of()
    same(f, {"realSeen": None, "realAvg": None, "fastSeen": 0.95})
    alike(f["pnl"]["real"], NOTHING, "fastShadow.pnl.real")
    assert [row["seenReal"] for row in f["rows"]] == [None, None]


def test_a_bet_of_no_contracts_has_no_price(home):
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 0, 8, 8 * 0.95, 0.03)
    bet(db, "KXBTC15M-1", W1, 0, 0.0)
    db.commit()
    assert fast_of()["realAvg"] is None


# ------------------------------------------------------------------ the lag
def test_the_lag_median_and_p90_by_hand(home):
    """The measured rows' non-null lags, sorted: 0.05, 0.08, 0.12, 0.20, 0.30. Median at index 2; the 90th percentile
    interpolated at 0.9 · 4 = 3.6: 0.20 + 0.6 · 0.10. BTC-3's NULL lag and the unread DOGE-1's 0.5 s are left out
    (with the latter the median would be 0.16)."""
    paired(home).close()
    lags = [0.05, 0.08, 0.12, 0.20, 0.30]
    want = {"median": 0.12, "p90": 0.20 + 0.6 * (0.30 - 0.20)}
    assert fast_entry.quantile(lags, 0.5) == pytest.approx(want["median"])
    assert fast_entry.quantile(lags, 0.9) == pytest.approx(want["p90"])
    alike(fast_of()["lag"], want, "fastShadow.lag")


def test_the_lag_of_an_even_number_interpolates(home):
    """Four lags (written out of order), sorted 0.1, 0.2, 0.4, 1.0: median at 1.5 → 0.3; p90 at 2.7 → 0.4 + 0.7 · 0.6."""
    db = paper_ledger(home)
    for i, lag in enumerate((1.0, 0.1, 0.4, 0.2)):
        fast(db, W1 + 482 + i, f"KXBTC15M-{i}", W1, 10, 5, 5, 5 * 0.95, 0.02, lag=lag)
    db.commit()
    alike(fast_of()["lag"], {"median": 0.3, "p90": 0.82}, "fastShadow.lag")


def test_no_lags_gives_nones(home):
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 5, 5, 5 * 0.95, 0.02, lag=None)
    fast(db, W1 + 483, "KXETH15M-1", W1, 10, 5, lag=0.4, unread=True)    # unread: its lag doesn't count
    db.commit()
    assert fast_of()["lag"] == {"median": None, "p90": None}


# ------------------------------------------------------------------ the P&L
def test_the_pnl_on_paper_and_for_real_by_hand(home):
    """Four settled rows. On paper: the settled rows that cost something, by window (XRP-3 bought nothing: counted, its
    window would make the standard error 187 not 216). For real: those rows' won and lost bets. ¢ per $10 with the
    standard error clustered by window."""
    paired(home).close()
    assert clustered_se(PAPER_WINDOWS) == pytest.approx(216.2395236740597, abs=1e-6)   # the hand arithmetic, once
    assert clustered_se(REAL_WINDOWS) == pytest.approx(208.29783493583244, abs=1e-6)
    pnl = fast_of()["pnl"]
    assert pnl["settled"] == 4
    alike(pnl["paper"], {"pnl": -6.49, "staked": 28.36, "perTen": 1000 * -6.49 / 28.36,
                         "se": clustered_se(PAPER_WINDOWS)}, "fastShadow.pnl.paper")
    alike(pnl["real"], {"pnl": -8.94, "staked": 18.84, "perTen": 1000 * -8.94 / 18.84,
                        "se": clustered_se(REAL_WINDOWS)}, "fastShadow.pnl.real")


def test_real_pnl_counts_only_settled_rows_won_or_lost_bets(home):
    """BTC-1 settled and its bet won: it counts. ETH-2 settled but its bet is still open, SOL-2 settled with no bet:
    left out. XRP-3's bet lost but its row is still open: left out (and from settled). One real window: no standard
    error. On paper the three settled rows count, over two windows."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 5, 8, 8 * 0.94, 0.04, seen=0.94, result="yes")      # +0.44
    bet(db, "KXBTC15M-1", W1, 5, 4.70, "won", 0.30)
    fast(db, W2 + 482, "KXETH15M-2", W2, 10, 3, 6, 6 * 0.95, 0.03, result="yes")                 # +0.27
    bet(db, "KXETH15M-2", W2, 3, 2.85, "open")
    fast(db, W2 + 483, "KXSOL15M-2", W2, 10, 0, 4, 4 * 0.96, 0.02, seen=0.96, result="no")       # −3.86
    fast(db, W3 + 482, "KXXRP15M-3", W3, 10, 2, 2, 2 * 0.95, 0.01)                               # open
    bet(db, "KXXRP15M-3", W3, 2, 1.90, "lost", -1.90)
    db.commit()
    pnl = fast_of()["pnl"]
    windows = [(8 - 7.52 - 0.04, 7.52), ((6 - 5.70 - 0.03) + (-3.84 - 0.02), 5.70 + 3.84)]
    assert pnl["settled"] == 3
    alike(pnl["paper"], {"pnl": 0.44 + 0.27 - 3.86, "staked": 7.52 + 9.54, "perTen": 1000 * -3.15 / 17.06,
                         "se": clustered_se(windows)}, "fastShadow.pnl.paper")
    alike(pnl["real"], {"pnl": 0.30, "staked": 4.70, "perTen": 1000 * 0.30 / 4.70, "se": None}, "fastShadow.pnl.real")


def test_no_settled_rows_no_pnl(home):
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 5, 5, 5 * 0.95, 0.02)
    bet(db, "KXBTC15M-1", W1, 5, 4.75, "won", 0.24)                      # its bet settled first: still not counted
    db.commit()
    alike(fast_of()["pnl"], {"settled": 0, "paper": NOTHING, "real": NOTHING}, "fastShadow.pnl")


# ------------------------------------------------------------------ unread rows
def test_a_table_of_only_unread_rows(home):
    """The bot has started (the first row's time) but every book read failed: nothing measured, so every count is 0 and
    every ratio null, and it is too early to tell rather than waiting for a restart."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, lag=None, unread=True)
    fast(db, W2 + 482, "KXBTC15M-2", W2, 10, 10, lag=12.0, unread=True)
    db.commit()
    f = fast_of()
    alike(f, {**EMPTY, "started": W1 + 482, "unread": 2,
              "verdict": {"state": "too-early", "text": F_TOO_EARLY.format(n=0, target=300), "orders": 0, "target": 300}})


# ------------------------------------------------------------------ the verdict
def spread(db, filled, extras):
    """One paired order a window (W1, W2, ...), each asking for 10 contracts and filling `filled` for real; `extras`:
    what each one's twin bought at the mark."""
    for i, (w, extra) in enumerate(zip((W1, W2, W3, W4), extras)):
        fast(db, w + 482, f"KXBTC15M-{i}", w, 10, filled, extra, extra * 0.95, 0.01 * extra)


def test_too_early_below_the_target(home):
    paired(home).close()
    v = fast_of()["verdict"]
    assert v == {"state": "too-early", "text": F_TOO_EARLY.format(n=6, target=300), "orders": 6, "target": 300}
    assert v["text"] == "Too early to tell: 6 of 300 orders paired on paper so far."


def test_too_early_one_order_short_of_a_small_target(home, monkeypatch):
    """Eight rows, but the two unread ones don't count towards the target."""
    paired(home).close()
    monkeypatch.setattr(dashboard, "FAST_SHADOW_TARGET", 7)
    f = fast_of()
    assert f["target"] == 7
    assert f["verdict"] == {"state": "too-early", "text": F_TOO_EARLY.format(n=6, target=7), "orders": 6, "target": 7}


def test_too_early_without_a_standard_error_even_at_the_target(home, monkeypatch):
    """Three orders, all in one window: the target is reached but the difference has no standard error yet."""
    db = paper_ledger(home)
    for i in range(3):
        fast(db, W1 + 482 + i, f"KXBTC15M-{i}", W1, 10, 2, 9, 9 * 0.95, 0.04)
    db.commit()
    monkeypatch.setattr(dashboard, "FAST_SHADOW_TARGET", 3)
    f = fast_of()
    assert f["diffSe"] is None and f["diff"] == pytest.approx(0.7)
    assert f["verdict"] == {"state": "too-early", "text": F_TOO_EARLY.format(n=3, target=3), "orders": 3, "target": 3}


def test_no_difference_when_the_range_includes_zero(home, monkeypatch):
    paired(home).close()
    monkeypatch.setattr(dashboard, "FAST_SHADOW_TARGET", 6)                # reached exactly: enough
    f = fast_of()
    assert f["diff"] - 1.96 * f["diffSe"] < 0 < f["diff"] + 1.96 * f["diffSe"]   # about −0.117 to +0.583
    assert f["verdict"] == {"state": "no-difference", "text": F_NO_DIFFERENCE, "orders": 6, "target": 6}


def test_faster_fills_more_when_the_whole_range_is_above_zero(home, monkeypatch):
    """Three windows, each filling 2 of 10 for real and 8, 9, 7 at the mark: +0.6 with a standard error of
    √(3/2 · (0² + 1² + 1²)) / 30 ≈ 0.058, so its range is about +0.49 to +0.71."""
    db = paper_ledger(home)
    spread(db, 2, (8, 9, 7))
    db.commit()
    monkeypatch.setattr(dashboard, "FAST_SHADOW_TARGET", 3)
    f = fast_of()
    assert f["diff"] == pytest.approx(0.6) and f["diffSe"] == pytest.approx(ratio_se_by_hand([(6, 10), (7, 10), (5, 10)]))
    assert f["diffSe"] == pytest.approx(math.sqrt(1.5 * 2) / 30)
    assert f["diff"] - 1.96 * f["diffSe"] > 0
    assert f["verdict"] == {"state": "faster-fills-more", "text": F_MORE, "orders": 3, "target": 3}


def test_faster_fills_less_when_the_whole_range_is_below_zero(home, monkeypatch):
    """The mirror image: 8 of 10 for real, 2, 1, 3 at the mark: −0.6, range about −0.71 to −0.49."""
    db = paper_ledger(home)
    spread(db, 8, (2, 1, 3))
    db.commit()
    monkeypatch.setattr(dashboard, "FAST_SHADOW_TARGET", 3)
    f = fast_of()
    assert f["diff"] == pytest.approx(-0.6) and f["diffSe"] == pytest.approx(math.sqrt(1.5 * 2) / 30)
    assert f["diff"] + 1.96 * f["diffSe"] < 0
    assert f["verdict"] == {"state": "faster-fills-less", "text": F_LESS, "orders": 3, "target": 3}


# ------------------------------------------------------------------ the rows listed
def test_the_rows_newest_first_with_every_field(home):
    """Each measured row: the ask the real order saw (its decision's) and the one at the mark, the paper limit, the real
    order's asked and filled, what the mark bought and its average price (null with none), the lag, the paper P&L
    (null while open) and how it ended: won or lost (its side against the market's result, even with nothing bought),
    or open. Unread rows aren't listed."""
    paired(home).close()
    rows = fast_of()["rows"]
    assert [row["ticker"] for row in rows] == [row["ticker"] for row in MAIN_ROWS]
    for i, (got, want) in enumerate(zip(rows, MAIN_ROWS)):
        assert set(got) == ROW_KEYS, got
        alike(got, want, f"fastShadow.rows[{i}]")


def test_at_most_50_rows_are_listed(home):
    assert dashboard.LIVE_ORDERS_SHOWN == 50
    db = paper_ledger(home)
    for i in range(55):
        ts = NOW - 50000 + 900 * i
        fast(db, ts, f"KXETH15M-{i:02d}", ts - 482, 10, 5, 6, 6 * 0.95, 0.02)
        if i % 10 == 9:   # a failed read just after it: never listed
            fast(db, ts + 1, f"KXSOL15M-{i:02d}", ts - 482, 10, 5, unread=True)
    db.commit()
    f = fast_of()
    assert [row["ticker"] for row in f["rows"]] == [f"KXETH15M-{i:02d}" for i in range(54, 4, -1)]
    assert f["orders"] == 55 and f["unread"] == 5                          # the counts still have every row


# ------------------------------------------------------------------ read only, and plain JSON
def test_reading_never_changes_the_ledger(home):
    paired(home).close()
    path = home.dir / "live-prod.db"
    before, stamp, files = path.read_bytes(), os.stat(path).st_mtime_ns, sorted(os.listdir(home.dir))
    assert fast_of()["orders"] == 6                                        # it did read the table
    assert path.read_bytes() == before and os.stat(path).st_mtime_ns == stamp
    assert sorted(os.listdir(home.dir)) == files                           # nothing new beside it
    assert not [n for n in os.listdir(home.dir) if n.endswith(("-journal", "-wal", "-shm"))]


def only_unread(home):
    """One pair whose book couldn't be read: started, but nothing measured."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 4, lag=None, unread=True)
    db.commit()
    return db


def nothing_bought(home):
    """One settled pair that bought nothing at the mark, whose real bet has no contracts: every average is null."""
    db = paper_ledger(home)
    fast(db, W1 + 482, "KXBTC15M-1", W1, 10, 10, seen=None, result="yes")
    bet(db, "KXBTC15M-1", W1, 0, 0.0)
    db.commit()
    return db


LEDGERS = {"no-table": lambda home: paper_ledger(home, shadow=False), "empty-table": paper_ledger, "paired": paired,
           "with-limitup": lambda home: measured(home, also=both), "only-unread": only_unread,
           "nothing-bought": nothing_bought}


@pytest.mark.parametrize("build", list(LEDGERS))
def test_the_reply_is_plain_json(home, build):
    """No NaN or infinity, and nothing JSON can't hold (a sqlite3.Row, say), whatever the ledger."""
    LEDGERS[build](home).close()
    r = dashboard.live_research("live-prod")
    assert "fastShadow" in r, sorted(r)
    json.dumps(r, allow_nan=False)


def test_the_route_serves_fast_shadow(home):
    paired(home).close()
    with serving() as base:
        served = get(base, "/api/live-research")
    assert "fastShadow" in served, sorted(served)
    assert served["fastShadow"] == json.loads(json.dumps(fast_of(), default=str))   # the clock is frozen
    assert served["fastShadow"]["orders"] == 6
