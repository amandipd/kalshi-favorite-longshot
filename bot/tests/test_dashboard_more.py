"""The dashboard's server side, past what test_dashboard.py covers: the cache, the mode list, Kalshi lookups,
every number state() computes, each HTTP route, and the command line. Nothing here touches the network.

    python -m pytest tests/test_dashboard_more.py -q
"""
import argparse
import base64
import contextlib
import http.client
import json
import runpy
import os
import sqlite3
import threading
import types
import urllib.error
import urllib.request
from collections import deque
from http.server import ThreadingHTTPServer

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from layout import BOT
from test_bot import W

NOW = W + 3 * 3600  # 3 pm ET, a Monday (Sep 28, 2026)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An empty state folder, the clock frozen at NOW, and Kalshi stubbed out."""
    clock = [NOW]
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: clock[0]))
    dashboard._cache.clear()
    calls = {"marks": [], "account": [], "history": []}
    curve = [None]  # what the stubbed history returns
    monkeypatch.setattr(dashboard, "marks", lambda env, tickers: calls["marks"].append((env, list(tickers))) or {})
    monkeypatch.setattr(dashboard, "account", lambda env: calls["account"].append(env) or {"total": 50.0, "crypto": 40.0, "positions": 1})
    monkeypatch.setattr(dashboard, "history", lambda env, since: calls["history"].append((env, since)) or curve[0])
    return types.SimpleNamespace(dir=tmp_path, clock=clock, calls=calls, curve=curve)


def mode_db(home, name, start=100.0):
    db = bot.connect(str(home.dir / f"{name}.db"))
    if start is not None:
        bot.set_start(db, start)
    return db


def add_bet(db, ticker, side="yes", price=0.95, contracts=3, status="won", pnl=None, settled=None, placed=None, fee=0.01):
    placed = placed if placed is not None else NOW - 3600
    if pnl is None and status != "open":
        pnl = contracts - contracts * price - fee if status == "won" else -(contracts * price + fee)
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status, pnl, settled_ts)"
               " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, ticker.split("-")[0], placed - 480, placed + 420, side, price, contracts, contracts * price, fee, placed, status,
                None if status == "open" else pnl, None if status == "open" else (settled if settled is not None else placed + 900)))
    db.commit()


# ------------------------------------------------------------------ cached
def test_cached_holds_a_value_until_its_time_is_up(home):
    calls = []

    def fn():
        calls.append(1)
        return len(calls)
    assert dashboard.cached("k", 10, fn) == 1
    home.clock[0] += 9.9
    assert dashboard.cached("k", 10, fn) == 1
    home.clock[0] += 0.1                      # exactly ttl old is stale
    assert dashboard.cached("k", 10, fn) == 2
    assert dashboard.cached("other", 10, fn) == 3   # another key is its own entry
    assert len(calls) == 3


def test_a_cached_call_that_fails_isnt_remembered(home):
    def boom():
        raise RuntimeError("kalshi down")
    with pytest.raises(RuntimeError):
        dashboard.cached("k", 10, boom)
    assert dashboard.cached("k", 10, lambda: "fine") == "fine"


# ------------------------------------------------------------------ modes
def test_modes_puts_the_paper_ledger_first_and_the_live_modes_only_while_there_is_none(home):
    for name in ("live-demo", "live-prod", "paper-prod"):
        mode_db(home, name)
    (home.dir / "halt.json").write_text("{}")
    (home.dir / "notes.txt").write_text("not a database")
    assert dashboard.modes() == ["live-prod", "live-demo"]   # no paper ledger yet: old data still renders
    for name in ("dry-prod", "dry-demo"):                    # a paper ledger: the live tabs (the real wallet) go
        mode_db(home, name)
    assert dashboard.modes() == ["dry-prod", "dry-demo"]


def test_modes_with_no_state_folder_is_empty(home, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(home.dir / "nowhere"))
    assert dashboard.modes() == []


@pytest.mark.parametrize("v, want", [(None, None), ("", None), ("0.96", 0.96), (0.5, 0.5), (0, 0.0), ("1", 1.0)])
def test_num(v, want):
    assert dashboard.num(v) == want


# ------------------------------------------------------------------ marks and account
class KalshiStub:
    """Stands in for kalshi.Kalshi: remembers how it was built and called."""
    instances = []
    market_list = {"markets": []}
    bal = {"balance": 5000, "balance_breakdown": [{"exchange_index": 0, "balance": "10.0000"}, {"exchange_index": 2, "balance": "40.0000"}]}
    pos = {"market_positions": [{}, {}, {}]}
    last_error = None

    def __init__(self, *args):
        self.args, self.calls = args, []
        KalshiStub.instances.append(self)

    def markets(self, **p):
        self.calls.append(("markets", p))
        return KalshiStub.market_list

    def balance(self):
        return KalshiStub.bal

    def positions(self, **p):
        return KalshiStub.pos

    def exchange_status(self):
        return {"exchange_index_statuses": [{"exchange_index": 2, "description": "Crypto & Commodities"}]}

    lists = {}  # path -> its pages, in order; a cursor "pN" asks for page N

    def get(self, path, params=None, auth=False):
        self.calls.append(("get", path, dict(params or {}), auth))
        pages = KalshiStub.lists.get(path)
        if pages is None:
            return None
        cursor = (params or {}).get("cursor")
        return pages[int(cursor[1:]) - 1] if cursor else pages[0]


@pytest.fixture
def kalshi_stub(monkeypatch):
    KalshiStub.instances = []
    KalshiStub.market_list = {"markets": []}
    KalshiStub.bal = {"balance": 5000, "balance_breakdown": [{"exchange_index": 0, "balance": "10.0000"}, {"exchange_index": 2, "balance": "40.0000"}]}
    KalshiStub.pos = {"market_positions": [{}, {}, {}]}
    KalshiStub.last_error = None
    KalshiStub.lists = {}
    monkeypatch.setattr(dashboard, "Kalshi", KalshiStub)
    return KalshiStub


def test_marks_reads_public_bid_and_ask_prices(kalshi_stub, monkeypatch):
    kalshi_stub.market_list = {"markets": [{"ticker": "A", "yes_bid_dollars": "0.9600", "yes_ask_dollars": "0.9700"},
                                           {"ticker": "B", "yes_bid_dollars": "", "yes_ask_dollars": None},
                                           {"ticker": "C"}]}
    got = dashboard.marks("prod", ["A", "B", "C"])
    assert got == {"A": (0.96, 0.97), "B": (None, None), "C": (None, None)}
    k = kalshi_stub.instances[0]
    assert k.args == ("prod",) and k.calls == [("markets", {"tickers": "A,B,C", "limit": 100})]  # public: no key


def test_marks_survives_kalshi_being_unreachable(kalshi_stub):
    kalshi_stub.market_list = None
    assert dashboard.marks("prod", ["A"]) == {}


def with_cfg(monkeypatch, **cfg):
    monkeypatch.setattr(bot, "load_env", lambda *a, **k: cfg)


def test_account_needs_a_key(kalshi_stub, monkeypatch):
    for cfg in ({}, {"KALSHI_API_KEY_ID": "id"}, {"KALSHI_PRIVATE_KEY_PATH": "/k.pem"}):
        with_cfg(monkeypatch, **cfg)
        assert dashboard.account("prod") == {"error": "no API key in .env"}
    assert kalshi_stub.instances == []


@pytest.mark.parametrize("cfg_env, asked, message", [("demo", "prod", "the key in .env is for demo, not prod"),
                                                     ("prod", "demo", "the key in .env is for prod, not demo"),
                                                     (None, "prod", "the key in .env is for demo, not prod")])
def test_account_wont_show_the_other_environments_balance(kalshi_stub, monkeypatch, cfg_env, asked, message):
    with_cfg(monkeypatch, KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem", **({"KALSHI_ENV": cfg_env} if cfg_env else {}))
    assert dashboard.account(asked) == {"error": message} and kalshi_stub.instances == []


def test_account_reads_the_balance_and_positions(kalshi_stub, monkeypatch):
    with_cfg(monkeypatch, KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
    assert dashboard.account("prod") == {"total": 50.0, "crypto": 40.0, "positions": 3, "held": 0.0, "value": 50.0, "updated": None}
    assert kalshi_stub.instances[0].args == ("prod", "id", "/k.pem")


def test_account_values_open_positions_and_reads_fractions_of_a_cent(kalshi_stub, monkeypatch):
    with_cfg(monkeypatch, KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
    kalshi_stub.bal = dict(kalshi_stub.bal, balance_dollars="50.1234", portfolio_value=518, updated_ts=1790727067)
    a = dashboard.account("prod")
    assert (a["total"], a["held"], a["updated"]) == (50.1234, 5.18, 1790727067)
    assert a["value"] == pytest.approx(55.3034)


def test_account_copes_with_unreadable_positions_and_balances(kalshi_stub, monkeypatch):
    with_cfg(monkeypatch, KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
    kalshi_stub.pos = None
    assert dashboard.account("prod")["positions"] == 0
    kalshi_stub.bal, kalshi_stub.last_error = None, "HTTP 401: bad key"
    assert dashboard.account("prod") == {"error": "HTTP 401: bad key"}
    kalshi_stub.bal, kalshi_stub.last_error = {"oops": 1}, None
    assert dashboard.account("prod") == {"error": "couldn't read the balance"}


# ------------------------------------------------------------------ the real account's value over time
def settlement(ticker, t, revenue, yes_cost, fee=0.01):
    return {"ticker": ticker, "settled_time": bot.iso(t), "revenue": revenue, "yes_total_cost_dollars": f"{yes_cost:.6f}",
            "no_total_cost_dollars": "0.000000", "fee_cost": f"{fee:.6f}"}


@pytest.fixture
def records(kalshi_stub, monkeypatch):
    """$235 cash and one open bet (cost $2.85, fee 1c) now; since W: three settlements, a deposit and a withdrawal."""
    with_cfg(monkeypatch, KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
    kalshi_stub.bal = {"balance": 23500, "balance_dollars": "235.0000", "portfolio_value": 300}
    kalshi_stub.pos = {"market_positions": [{"ticker": "OPEN", "market_exposure_dollars": "2.850000", "fees_paid_dollars": "0.010000",
                                             "last_updated_ts": bot.iso(W + 3000)}]}
    kalshi_stub.lists = {
        "/portfolio/deposits": [{"deposits": [{"amount_cents": 14000, "created_ts": W + 2000, "status": "applied"},
                                              {"amount_cents": 5000, "created_ts": W + 2100, "status": "returned"},
                                              {"amount_cents": 9999, "created_ts": W - 5000, "status": "applied"}]}],
        "/portfolio/withdrawals": [{"withdrawals": [{"amount_cents": 1000, "created_ts": W + 2500, "finalized_ts": W + 2600,
                                                     "status": "applied"}]}],
        "/portfolio/settlements": [{"settlements": [settlement("A", W + 900, 300, 2.85), settlement("B", W + 910, 0, 2.91)], "cursor": "p2"},
                                   {"settlements": [settlement("C", W + 1800, 300, 2.88)]}],
    }
    return kalshi_stub


def test_history_walks_back_from_today_through_kalshis_records(records):
    got = dashboard.history("prod", W - 60)
    want = [[W - 60, 110.53, 0, "start"],
            [W + 910, 107.75, 0, "1 won · 1 lost"],      # two settlements in one minute are one point: +0.14 - 2.92
            [W + 1800, 107.86, 0, "1 won"],
            [W + 2000, 247.86, 140.0, "deposit"],          # the returned deposit, and the one before W, don't count
            [W + 2600, 237.86, -10.0, "withdrawal"],       # when it went through, not when it was asked for
            [W + 3000, 237.85, 0, "1 bet placed"]]         # the open bet's fee; the bet itself is valued at cost
    assert [p[0] for p in got] == [p[0] for p in want] and [p[2:] for p in got] == [p[2:] for p in want]
    assert [p[1] for p in got] == pytest.approx([p[1] for p in want])


def test_history_reads_every_page_of_settlements_since_the_start(records):
    dashboard.history("prod", W - 60)
    gets = [c for c in records.instances[0].calls if c[0] == "get"]
    settles = [c for c in gets if c[1] == "/portfolio/settlements"]
    assert [c[2] for c in settles] == [{"min_ts": int(W - 60), "limit": 200}, {"min_ts": int(W - 60), "limit": 200, "cursor": "p2"}]
    assert all(c[3] for c in gets)                         # all signed: these are your records


@pytest.mark.parametrize("broken", ["/portfolio/deposits", "/portfolio/withdrawals", "/portfolio/settlements", "balance", "positions"])
def test_history_is_none_when_any_record_cant_be_read(records, broken):
    if broken == "balance":
        records.bal = None
    elif broken == "positions":
        records.pos = None
    else:
        records.lists[broken] = None
    assert dashboard.history("prod", W - 60) is None


def test_history_needs_the_key_for_that_environment(records, monkeypatch):
    with_cfg(monkeypatch, KALSHI_ENV="demo", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")
    assert dashboard.history("prod", W - 60) is None


def test_history_leaves_out_settlements_and_fees_from_before_the_start(records):
    records.lists["/portfolio/settlements"] = [{"settlements": [settlement("OLD", W - 100, 300, 2.85)]}]
    records.pos = {"market_positions": [
        {"ticker": "EARLIER", "market_exposure_dollars": "2.850000", "fees_paid_dollars": "0.010000", "last_updated_ts": bot.iso(W - 100)},
        {"ticker": "NO-FEE", "market_exposure_dollars": "1.000000", "fees_paid_dollars": "0.000000", "last_updated_ts": bot.iso(W + 100)}]}
    assert [p[3] for p in dashboard.history("prod", W - 60)] == ["start", "deposit", "withdrawal"]


def test_a_list_that_never_ends_is_read_50_pages_deep_and_no_further(kalshi_stub):
    kalshi_stub.lists = {"/x": [{"rows": [i], "cursor": f"p{i + 2}"} for i in range(60)]}
    k = kalshi_stub()
    assert dashboard.pages(k, "/x", "rows") == list(range(50)) and len(k.calls) == 50


# ------------------------------------------------------------------ state()
def test_a_live_account_draws_its_real_value_up_to_now(home, monkeypatch):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", placed=NOW - 7200)
    home.curve[0] = [[NOW - 7260, 100.0, 0, "start"], [NOW - 6000, 102.0, 0, "1 won"]]
    monkeypatch.setattr(dashboard, "account", lambda env: {"total": 240.0, "crypto": 240.0, "positions": 0, "held": 1.5, "value": 241.5})
    s = dashboard.state("live-prod")
    assert home.calls["history"] == [("prod", NOW - 7260)]   # from a minute before the bot's first bet
    assert s["kalshiCurve"] == [[NOW - 7260, 100.0, 0, "start"], [NOW - 6000, 102.0, 0, "1 won"], [NOW, 241.5, 0, "now"]]
    assert home.curve[0][-1] == [NOW - 6000, 102.0, 0, "1 won"]   # the cached history isn't changed by adding "now"


def test_no_real_curve_without_a_bet_or_a_readable_account(home):
    db = mode_db(home, "live-prod")
    assert dashboard.state("live-prod")["kalshiCurve"] is None and home.calls["history"] == []   # no bets yet
    add_bet(db, "KXBTC15M-1")
    home.curve[0] = [[NOW - 3660, 100.0, 0, "start"]]
    assert dashboard.state("live-prod")["kalshiCurve"] is None   # the stubbed account has no value to end it on
    mode_db(home, "dry-prod")
    assert "kalshiCurve" not in dashboard.state("dry-prod")      # a paper mode never draws the wallet's curve


def test_an_account_with_no_bets_yet(home, monkeypatch):
    monkeypatch.setattr(dashboard, "RESEARCH", str(home.dir))   # no backtest here: the sim reads as missing
    db = mode_db(home, "dry-demo")
    s = dashboard.state("dry-demo")
    assert (s["mode"], s["live"], s["env"], s["modes"]) == ("dry-demo", False, "demo", ["dry-demo"])   # its own tab now
    assert (s["start"], s["bankroll"], s["unrealized"], s["openCost"]) == (100.0, 100.0, 0.0, 0.0)
    assert (s["wins"], s["losses"], s["need"], s["winShare"], s["fees"], s["maxDrop"]) == (0, 0, None, None, 0.0, 0.0)
    assert (s["day"], s["dayBets"], s["nextBet"], s["curve"]) == (0.0, 0, 1.5, [])   # 1.5% of $100
    assert (s["openBets"], s["recentBets"], s["bySeries"], s["decisions"], s["errors"]) == ([], [], [], [], [])
    assert (s["heartbeat"], s["halt"], s["now"]) == (None, None, NOW)
    assert "kalshi" not in s and "kalshiCurve" not in s and s["sim"] is None   # a paper mode: the wallet stays off
    assert home.calls == {"marks": [], "account": [], "history": []}  # nothing to look up


def test_only_live_modes_look_up_the_real_account(home):
    mode_db(home, "dry-prod")
    mode_db(home, "live-prod")
    assert "kalshi" not in dashboard.state("dry-prod") and home.calls["account"] == []
    s = dashboard.state("live-prod")
    assert (s["live"], s["env"], s["kalshi"]) == (True, "prod", {"total": 50.0, "crypto": 40.0, "positions": 1})
    assert home.calls["account"] == ["prod"]


def test_the_account_lookup_is_cached_for_10_seconds(home):
    mode_db(home, "live-prod")
    dashboard.state("live-prod")
    home.clock[0] += 9
    dashboard.state("live-prod")
    assert home.calls["account"] == ["prod"]
    home.clock[0] += 2
    dashboard.state("live-prod")
    assert home.calls["account"] == ["prod", "prod"]


def test_the_limits_come_from_the_bots_own_constants(home, monkeypatch):
    """The page shows what the bot enforces, so it must never carry its own copy of the numbers."""
    mode_db(home, "live-prod")
    lim = dashboard.state("live-prod")["limits"]
    assert lim == {"betPct": 0.015, "windowPct": 0.10, "ordersPerWindow": 20, "ordersPerDay": 600,
                   "minCash": pytest.approx(1 / 0.015), "dayDrop": 0.35, "halfStart": 0.50, "windowLosses": 8,
                   "settleLag": 1800, "persist": 300, "orderErrors": 3,
                   "minute": 8, "lo": 0.92, "hi": 0.999, "limitUp": 0.01, "shadowUp": 0.01, "grace": 45, "spreadMax": 0.02, "lateMid": 0.50,
                   "jump": 0.10, "orderDeadline": 60, "bookMaxAge": 15, "restingEvery": 15, "orderConnect": 3.05, "orderAnswer": 5}
    monkeypatch.setattr(bot, "HALT_DAY_DROP", 0.12)
    monkeypatch.setattr(bot, "MAX_ORDERS_PER_WINDOW", 12)
    monkeypatch.setattr(bot, "SPREAD_MAX", 0.03)
    changed = dashboard.state("live-prod")["limits"]
    assert changed["dayDrop"] == 0.12 and changed["ordersPerWindow"] == 12 and changed["spreadMax"] == 0.03


def test_the_groups_it_trades_come_from_the_bot(home, monkeypatch):
    mode_db(home, "live-prod")
    assert dashboard.state("live-prod")["groups"] == ["crypto", "metals", "energy"]
    monkeypatch.setattr(bot, "EDGE_GROUPS", ("metals",))
    assert dashboard.state("live-prod")["groups"] == ["metals"]


def test_the_halt_floor_reference_is_the_start_until_a_resume_moves_it(home):
    db = mode_db(home, "live-prod", start=100.0)
    assert dashboard.state("live-prod")["haltBase"] == 100.0
    add_bet(db, "KXBTC15M-1", status="lost", pnl=-30.0)
    bot.clear_halt(NOW, [db])                       # a resume at $70 re-bases the floor
    assert dashboard.state("live-prod")["haltBase"] == 70.0
    bot.set_start(db, 250.0)                        # a new start forgets the old reference
    db.commit()
    assert dashboard.state("live-prod")["haltBase"] == 250.0


def test_the_heartbeat_and_a_halt_come_through(home):
    db = mode_db(home, "live-prod")
    bot.set_meta(db, "heartbeat", NOW - 7)
    db.commit()
    bot.set_halt(NOW - 60, "testing", "you")
    s = dashboard.state("live-prod")
    assert s["heartbeat"] == NOW - 7 and s["halt"] == {"ts": bot.iso(NOW - 60), "reason": "testing", "by": "you"}


def test_wins_losses_fees_and_the_break_even_win_rate(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", price=0.96, contracts=3, status="won")
    add_bet(db, "KXBTC15M-2", price=0.94, contracts=2, status="lost", fee=0.02)
    add_bet(db, "KXGOLD15M-1", price=0.90, contracts=1, status="open", fee=0.03)
    s = dashboard.state("live-prod")
    assert (s["wins"], s["losses"], len(s["openBets"])) == (1, 1, 1)
    assert s["fees"] == pytest.approx(0.01 + 0.02 + 0.03)          # every bet's, open ones too
    assert s["need"] == pytest.approx((3 * 0.96 + 0.01 + 2 * 0.94 + 0.02) / 5)   # settled cost and fees per contract
    assert s["winShare"] == pytest.approx(3 / 5)   # ... against the settled contracts that won: per contract too, open ones out
    assert s["openCost"] == pytest.approx(0.90 + 0.03)
    assert s["bankroll"] == pytest.approx(100 + (3 - 2.88 - 0.01) + (-(1.88 + 0.02)))


def test_the_bankroll_curve_and_the_worst_drop(home):
    db = mode_db(home, "live-prod")
    for i, (pnl, at) in enumerate([(5.0, 100), (-20.0, 200), (-10.0, 300), (30.0, 400)]):   # 105, 85, 75, 105
        add_bet(db, f"KXBTC15M-{i}", status="won" if pnl > 0 else "lost", pnl=pnl, settled=NOW - 10000 + at, placed=NOW - 20000 + 10 * i)
    s = dashboard.state("live-prod")
    assert s["curve"] == [[NOW - 20000, 100.0], [NOW - 9900, 105.0], [NOW - 9800, 85.0], [NOW - 9700, 75.0], [NOW - 9600, 105.0]]
    assert s["maxDrop"] == pytest.approx(1 - 75 / 105)              # from the 105 peak to the 75 trough


def test_the_curve_follows_settlement_order_not_bet_order(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", pnl=-5.0, status="lost", placed=NOW - 5000, settled=NOW - 1000)   # bet first, settled last
    add_bet(db, "KXBTC15M-2", pnl=+2.0, status="won", placed=NOW - 4000, settled=NOW - 2000)
    assert [v for _, v in dashboard.state("live-prod")["curve"]] == [100.0, 102.0, 97.0]


def test_the_last_24_hours(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-old", pnl=-9.0, status="lost", placed=NOW - 2 * 86400, settled=NOW - 86400 - 1)
    add_bet(db, "KXBTC15M-edge", pnl=-1.0, status="lost", placed=NOW - 86400, settled=NOW - 86400)       # exactly a day ago: in
    add_bet(db, "KXBTC15M-new", pnl=+0.5, status="won", placed=NOW - 100, settled=NOW - 50)
    add_bet(db, "KXBTC15M-open", status="open", placed=NOW - 10)
    s = dashboard.state("live-prod")
    assert s["day"] == pytest.approx(-0.5) and s["dayBets"] == 3


def test_open_bets_are_valued_at_what_they_would_sell_for(home, monkeypatch):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-Y", side="yes", price=0.95, contracts=3, status="open")
    add_bet(db, "KXGOLD15M-N", side="no", price=0.97, contracts=3, status="open")
    add_bet(db, "KXETH15M-NONE", side="yes", price=0.93, contracts=3, status="open")   # Kalshi has no quote for it
    monkeypatch.setattr(dashboard, "marks", lambda env, tickers: {"KXBTC15M-Y": (0.97, 0.98), "KXGOLD15M-N": (0.01, 0.02)})
    s = dashboard.state("live-prod")
    by = {b["ticker"]: b for b in s["openBets"]}
    y, n, none = by["KXBTC15M-Y"], by["KXGOLD15M-N"], by["KXETH15M-NONE"]
    assert y["mark"] == 0.97 and y["unrealized"] == pytest.approx(3 * 0.97 - 2.85 - 0.01)   # YES sells at the bid
    assert n["mark"] == 0.98 and n["unrealized"] == pytest.approx(3 * 0.98 - 2.91 - 0.01)   # NO sells at 1 - the ask
    assert none["mark"] is None and none["unrealized"] is None
    assert s["unrealized"] == pytest.approx(y["unrealized"] + n["unrealized"])                # unpriced ones add nothing


def test_a_no_bet_with_no_ask_has_no_mark(home, monkeypatch):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXGOLD15M-N", side="no", status="open")
    monkeypatch.setattr(dashboard, "marks", lambda env, tickers: {"KXGOLD15M-N": (0.5, None)})
    assert dashboard.state("live-prod")["openBets"][0]["mark"] is None


def test_marks_are_cached_for_10_seconds_per_set_of_open_bets(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", status="open")
    dashboard.state("live-prod")
    home.clock[0] += 9
    dashboard.state("live-prod")
    assert len(home.calls["marks"]) == 1 and home.calls["marks"][0] == ("prod", ["KXBTC15M-1"])
    add_bet(db, "KXBTC15M-2", status="open")                     # a new open bet is a new lookup right away
    dashboard.state("live-prod")
    assert len(home.calls["marks"]) == 2 and home.calls["marks"][1][1] == ["KXBTC15M-1", "KXBTC15M-2"]
    home.clock[0] += 11
    dashboard.state("live-prod")
    assert len(home.calls["marks"]) == 3


def test_recent_bets_are_the_newest_150_first(home):
    db = mode_db(home, "live-prod")
    for i in range(200):
        add_bet(db, f"KXBTC15M-{i:03d}", placed=NOW - 100000 + i, settled=NOW - 50000 + i, pnl=0.01, status="won")
    s = dashboard.state("live-prod")
    assert len(s["recentBets"]) == 150
    assert s["recentBets"][0]["ticker"] == "KXBTC15M-199" and s["recentBets"][-1]["ticker"] == "KXBTC15M-050"
    assert s["wins"] == 200                                       # the tallies still count all of them


def test_results_by_market_worst_first(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", status="won", pnl=0.10, price=0.95, contracts=3)
    add_bet(db, "KXBTC15M-2", status="lost", pnl=-2.90, price=0.96, contracts=3)
    add_bet(db, "KXGOLD15M-1", status="won", pnl=0.20, price=0.90, contracts=2)
    add_bet(db, "KXETH15M-1", status="open")
    rows = dashboard.state("live-prod")["bySeries"]
    assert [r["series"] for r in rows] == ["KXBTC15M", "KXGOLD15M"]      # the open bet's series isn't listed; worst first
    btc = rows[0]
    assert (btc["n"], btc["wins"]) == (2, 1) and btc["pnl"] == pytest.approx(-2.80) and btc["staked"] == pytest.approx(2.85 + 2.88)


def test_decisions_are_the_newest_200_first(home):
    db = mode_db(home, "live-prod")
    for i in range(250):
        db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
                   (NOW - 1000 + i, f"KXBTC15M-{i:03d}", "KXBTC15M", "yes", 0.5, "skip", "why"))
    db.commit()
    d = dashboard.state("live-prod")["decisions"]
    assert len(d) == 200 and d[0]["ticker"] == "KXBTC15M-249" and d[-1]["ticker"] == "KXBTC15M-050"
    assert set(d[0]) == {"ts", "ticker", "series", "fav_side", "fav_price", "action", "reason"}


def test_decisions_at_the_same_moment_keep_their_order_newest_first(home):
    db = mode_db(home, "live-prod")
    for t in ("A", "B", "C"):
        db.execute("INSERT INTO decisions (ts, ticker, action, reason) VALUES (?,?, 'skip', 'x')", (NOW, f"KXBTC15M-{t}"))
    db.commit()
    assert [d["ticker"] for d in dashboard.state("live-prod")["decisions"]] == ["KXBTC15M-C", "KXBTC15M-B", "KXBTC15M-A"]


def test_only_failed_orders_are_listed_newest_first(home):
    db = mode_db(home, "live-prod")
    for i, status in enumerate([201, 200, 400, None, 500, 201, 429]):
        db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
                   (NOW - 100 + i, f"KXBTC15M-{i}", "c", "{}", status, '"r"'))
    db.commit()
    errors = dashboard.state("live-prod")["errors"]
    assert [(e["ticker"], e["http_status"]) for e in errors] == [("KXBTC15M-6", 429), ("KXBTC15M-4", 500), ("KXBTC15M-3", None), ("KXBTC15M-2", 400)]
    assert set(errors[0]) == {"ts", "ticker", "http_status", "response"}


def test_at_most_30_failed_orders_are_listed(home):
    db = mode_db(home, "live-prod")
    for i in range(45):
        db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
                   (NOW - 1000 + i, f"KXBTC15M-{i:02d}", "c", "{}", 500, '"boom"'))
    db.commit()
    errors = dashboard.state("live-prod")["errors"]
    assert len(errors) == 30 and errors[0]["ticker"] == "KXBTC15M-44" and errors[-1]["ticker"] == "KXBTC15M-15"


def order(db, ts, ticker, side="bid", count="15", price="0.9300", status=201, response='{"fill_count": "4.00"}'):
    request = json.dumps({"ticker": ticker, "side": side, "count": count, "price": price, "time_in_force": "immediate_or_cancel"})
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, "c", request, status, response))


def row(status, response, **request):
    req = {"side": "bid", "count": "15", "price": "0.9300", **request}
    return {"ts": NOW, "ticker": "KXXRP15M-26OCT100530-30", "request": json.dumps(req), "http_status": status, "response": response}


def test_an_order_row_is_the_favorite_it_bought_and_how_much_filled():
    yes = dashboard.order_row(row(201, '{"fill_count": "4.00", "average_fill_price": "0.9300"}'))
    assert yes == {"ts": NOW, "ticker": "KXXRP15M-26OCT100530-30", "series": "KXXRP15M", "side": "yes", "price": 0.93,
                   "asked": 15.0, "filled": 4.0, "error": None}
    no = dashboard.order_row(row(201, '{"fill_count": "0.00"}', side="ask", price="0.0750", count="16"))
    assert (no["side"], no["price"], no["asked"], no["filled"]) == ("no", 0.925, 16.0, 0.0)          # an ask on YES buys NO at 1 - it
    assert dashboard.order_row(row(201, '{"order_id": "x"}'))["filled"] == 0.0                     # no fill count: nothing filled
    assert dashboard.order_row(row(201, '{"fill_count": "3.40"}'))["filled"] == 3.4                 # fractions of a contract


def test_an_order_row_says_why_an_order_failed():
    refused = dashboard.order_row(row(400, '{"error": {"code": "insufficient_balance", "message": "insufficient balance"}}'))
    assert (refused["filled"], refused["error"]) == (None, "insufficient balance")
    assert dashboard.order_row(row(None, '"network error: timed out"'))["error"] == "no answer from Kalshi"
    assert dashboard.order_row(row(500, '{"detail": "oops"}'))["error"] == "HTTP 500"
    assert dashboard.order_row(row(503, '{"error": "busy"}'))["error"] == "HTTP 503"                 # an error that isn't an object
    assert dashboard.order_row(row(502, None))["error"] == "HTTP 502"                               # no answer stored
    assert dashboard.order_row(row(201, "not json"))["error"] == "HTTP 201"                         # an answer it can't read
    odd = dashboard.order_row(row(201, '{"fill_count": "1.00"}', side="sideways"))
    assert (odd["side"], odd["price"]) == (None, None)
    assert dashboard.order_row(row(201, '{"fill_count": "1.00"}', price=None))["price"] is None


def test_the_live_tab_lists_the_latest_buy_orders_and_the_last_days_fill_rate(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 90_000, "KXBTC15M-OLD", response='{"fill_count": "15.00"}')                  # over a day ago
    order(db, NOW - 300, "KXETH15M-A", response='{"fill_count": "0.00"}')
    order(db, NOW - 200, "KXXRP15M-A", side="ask", price="0.0750")                                # 4 of 15
    order(db, NOW - 100, "KXDOGE15M-A", status=400, response='{"error": {"message": "insufficient balance"}}')
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (NOW - 50, "KXXRP15M-A", "c", '{"cancel": "abc"}', 200, '{}'))                     # a cancel, not an order
    db.commit()
    s = dashboard.state("live-prod")
    assert [o["ticker"] for o in s["orders"]] == ["KXDOGE15M-A", "KXXRP15M-A", "KXETH15M-A", "KXBTC15M-OLD"]
    assert s["fills"] == {"orders": 3, "asked": 45.0, "filled": 4.0, "none": 2}                  # the refused and the empty one


def test_at_most_30_orders_are_listed(home):
    db = mode_db(home, "live-prod")
    for i in range(35):
        order(db, NOW - 1000 + i, f"KXBTC15M-{i:02d}")
    db.commit()
    s = dashboard.state("live-prod")
    assert len(s["orders"]) == dashboard.ORDERS_SHOWN == 30 and s["orders"][0]["ticker"] == "KXBTC15M-34"
    assert s["fills"]["orders"] == 35                                                            # the fill rate counts every one today


def test_the_next_bet_follows_the_bankroll(home):
    db = mode_db(home, "live-prod", start=1000.0)
    assert dashboard.state("live-prod")["nextBet"] == 15.0                 # 1.5% of $1,000: no $10 cap since Oct 10
    add_bet(db, "KXBTC15M-1", status="lost", pnl=-950.0)
    assert dashboard.state("live-prod")["nextBet"] == 0.75                 # 1.5% of the $50 left


@pytest.mark.parametrize("now, active, what", [
    (bot.ts("2026-10-28T17:00:00Z"), False, "Fed decision"),   # coming up
    (bot.ts("2026-10-28T18:00:00Z"), True, "Fed decision"),    # it starts
    (bot.ts("2026-10-28T19:29:59Z"), True, "Fed decision"),
    (bot.ts("2026-10-28T19:30:00Z"), False, "Fed decision"),   # over: the next one is December's
])
def test_the_next_blackout(home, now, active, what):
    mode_db(home, "live-prod")
    home.clock[0] = now
    b = dashboard.state("live-prod")["blackout"]
    starts = "2026-10-28T18:00:00Z" if now < bot.ts("2026-10-28T19:30:00Z") else "2026-12-09T19:00:00Z"
    assert (b["what"], b["active"], b["from"]) == (what, active, bot.ts(starts))


def test_no_blackout_once_they_are_all_past(home):
    mode_db(home, "live-prod")
    home.clock[0] = bot.ts("2027-12-09T00:00:00Z")
    assert dashboard.state("live-prod")["blackout"] is None


# ------------------------------------------------------------------ HTTP
@contextlib.contextmanager
def serving():
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def fetch(base, path, method="GET"):
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, method=method), timeout=5) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_the_page_is_served_at_both_addresses_uncached(home):
    with serving() as base:
        for path in ("/", "/index.html"):
            status, headers, body = fetch(base, path)
            assert status == 200 and headers["Content-Type"] == "text/html; charset=utf-8"
            assert headers["Cache-Control"] == "no-store" and int(headers["Content-Length"]) == len(body)
            assert b"Favorites Bot" in body
            assert body == open(dashboard.PAGE, "rb").read()


def test_the_state_is_json_and_uncached(home):
    mode_db(home, "live-prod")
    with serving() as base:
        status, headers, body = fetch(base, "/api/state")
    assert status == 200 and headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
    assert json.loads(body)["mode"] == "live-prod"


def test_with_no_accounts_yet_the_state_says_so(home):
    with serving() as base:
        assert json.loads(fetch(base, "/api/state")[2]) == {"modes": [], "halt": None}
        bot.set_halt(NOW, "early", "you")
        assert json.loads(fetch(base, "/api/state")[2])["halt"]["reason"] == "early"


def test_a_mode_can_be_chosen_by_name_and_unknown_ones_fall_back(home):
    for name in ("live-prod", "live-demo"):
        mode_db(home, name)
    with serving() as base:
        assert json.loads(fetch(base, "/api/state?mode=live-demo")[2])["mode"] == "live-demo"
        for bad in ("nope", "", "../../etc/passwd", "live-prod.db", "dry-prod", "paper-prod"):   # only modes that exist
            assert json.loads(fetch(base, f"/api/state?mode={bad}")[2])["mode"] == "live-prod"


def test_with_a_paper_ledger_the_live_names_fall_back_to_it(home):
    for name in ("live-prod", "live-demo", "dry-prod"):
        mode_db(home, name)
    with serving() as base:
        assert json.loads(fetch(base, "/api/state?mode=dry-prod")[2])["mode"] == "dry-prod"
        for gone in ("live-prod", "live-demo", "nope"):   # the wallet's tabs go while the paper ledger exists
            assert json.loads(fetch(base, f"/api/state?mode={gone}")[2])["mode"] == "dry-prod"


@pytest.mark.parametrize("method, path", [("GET", "/nope"), ("GET", "/api"), ("GET", "/api/halt"), ("GET", "/api/resume"),
                                          ("POST", "/"), ("POST", "/api/state"), ("POST", "/api/resume"), ("POST", "/api/halt/extra")])
def test_anything_else_is_a_404_and_changes_nothing(home, method, path):
    mode_db(home, "live-prod")
    with serving() as base:
        status, headers, body = fetch(base, path, method)
    assert status == 404 and json.loads(body) == {"error": "not found"} and bot.halt_info() is None


def test_the_halt_button_halts_once_and_reports_it(home):
    mode_db(home, "live-prod")
    with serving() as base:
        status, _, body = fetch(base, "/api/halt", "POST")
        first = json.loads(body)["halt"]
        assert status == 200 and first == {"ts": bot.iso(NOW), "reason": "halted from the dashboard", "by": "you"}
        home.clock[0] += 60
        assert json.loads(fetch(base, "/api/halt", "POST")[2])["halt"] == first    # pressing it again changes nothing
    assert bot.halt_info() == first


def test_a_halt_from_the_page_is_read_by_the_bot(home):
    """One file: the same halt the bot's --status, --resume and every mode see."""
    mode_db(home, "live-prod")
    with serving() as base:
        fetch(base, "/api/halt", "POST")
    assert bot.halt_info()["by"] == "you"
    assert bot.clear_halt(NOW, [])["reason"] == "halted from the dashboard" and bot.halt_info() is None


def test_a_broken_database_fails_that_request_not_the_server(home):
    (home.dir / "live-prod.db").write_text("this is not a database")
    with serving() as base:
        with pytest.raises((urllib.error.URLError, http.client.HTTPException, ConnectionError)):
            fetch(base, "/api/state")
        assert fetch(base, "/")[0] == 200            # still up
        assert fetch(base, "/api/halt", "POST")[0] == 200


# ------------------------------------------------------------------ the command line
@pytest.fixture
def launched(monkeypatch):
    seen = {}

    class Server:
        def __init__(self, address, handler):
            seen["address"], seen["handler"] = address, handler

        def serve_forever(self):
            seen["served"] = True

    monkeypatch.setattr(dashboard, "ThreadingHTTPServer", Server)
    monkeypatch.setattr(bot, "STATE", bot.STATE)   # restored afterwards: --state changes it
    return seen


def run_main(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["dashboard.py", *argv])
    dashboard.main()


def test_by_default_only_this_computer_can_open_it(launched, monkeypatch, capsys):
    run_main(monkeypatch)
    assert launched["address"] == ("127.0.0.1", 8080) and launched["handler"] is dashboard.Handler and launched["served"]
    assert capsys.readouterr().out == "dashboard on http://localhost:8080\n"


def test_lan_opens_it_to_the_home_network_and_says_so(launched, monkeypatch, capsys):
    run_main(monkeypatch, "--lan", "--port", "9090")
    assert launched["address"] == ("0.0.0.0", 9090)
    assert "dashboard on http://localhost:9090 (and this computer's address on your network)" in capsys.readouterr().out


def test_state_points_it_at_another_folder(launched, monkeypatch):
    run_main(monkeypatch, "--state", "/somewhere/else")
    assert bot.STATE == "/somewhere/else"


def test_a_port_must_be_a_number(launched, monkeypatch):
    with pytest.raises(SystemExit) as e:
        run_main(monkeypatch, "--port", "eighty")
    assert e.value.code == 2


@pytest.mark.parametrize("script", ["the module", "the front door"])
def test_ctrl_c_stops_the_dashboard_quietly(monkeypatch, capsys, script):
    """Run as a script (kalshi_bot/web/dashboard.py, or the dashboard.py beside the package that starts it) and
    interrupted before it opens a port: no traceback, nothing printed."""
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self, *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    runpy.run_path(dashboard.__file__ if script == "the module" else os.path.join(BOT, "dashboard.py"), run_name="__main__")
    assert capsys.readouterr().out == ""


# ------------------------------------------------------------------ the live markets, read from Kalshi
class Exchange:
    """Kalshi's public market data for the live feed: three 15-minute series (and a test and a daily one it must skip),
    each with a market in the current window and one from the window before."""
    SERIES = {"KXBTC15M": ["KXBTC15M-A"], "KXGOLD15M": ["KXGOLD15M-A"], "KXCRYPTOLEAD15M": ["KXCRYPTOLEAD15M-A-SOL"]}

    def __init__(self, window=W):
        self.window, self.calls, self.down = window, [], False
        self.prices = {}   # ticker -> (yes bid, yes ask)

    def series(self):
        self.calls.append(("series",))
        return None if self.down else {"series": [
            {"ticker": "KXBTC15M", "frequency": "fifteen_min", "category": "Crypto"},
            {"ticker": "KXGOLD15M", "frequency": "fifteen_min", "category": "Commodities"},
            {"ticker": "KXCRYPTOLEAD15M", "frequency": "fifteen_min", "category": "Crypto"},
            {"ticker": "KXBTC15MTEST", "frequency": "fifteen_min", "category": "Crypto"},
            {"ticker": "KXBTCD", "frequency": "daily", "category": "Crypto"}]}

    def raw(self, ticker, w):
        bid, ask = self.prices.get(ticker, (0.95, 0.96))
        return {"ticker": ticker, "open_time": bot.iso(w), "close_time": bot.iso(w + 900), "status": "active", "floor_strike": 100.5,
                "yes_bid_dollars": f"{bid:.4f}", "yes_ask_dollars": f"{ask:.4f}", "last_price_dollars": "0.9500",
                "yes_bid_size_fp": "10.00", "yes_ask_size_fp": "5.00", "volume_fp": "123.00", "open_interest_fp": "45.00"}

    def markets(self, **p):
        self.calls.append(("markets", p))
        if self.down:
            return None
        if "series_ticker" in p:
            s = p["series_ticker"]
            return {"markets": [self.raw(t, self.window) for t in self.SERIES.get(s, [])] + [self.raw(s + "-OLD", self.window - 900)]}
        return {"markets": [self.raw(t, self.window) for t in p["tickers"].split(",")]}

    def candlesticks(self, tickers, start, end):
        self.calls.append(("candles", tuple(tickers), start, end))
        return None if self.down else {"markets": [{"market_ticker": t, "candlesticks": [
            {"end_period_ts": start + 60 * k, "yes_bid": {"close_dollars": "0.9000"}, "yes_ask": {"close_dollars": "0.9200"}} for k in (1, 2)]}
            for t in tickers]}

    def orderbook(self, ticker):
        self.calls.append(("book", ticker))
        return None if self.down else {"orderbook_fp": {"yes_dollars": [["0.95", "10"], ["0.94", "3"]], "no_dollars": [["0.04", "5"]]}}

    def count(self, kind, key=None):
        return sum(1 for c in self.calls if c[0] == kind and (key is None or key in c[1]))


def quiet(k):
    """A feed on a fake exchange that never starts its background thread: the tests step it by hand."""
    f = dashboard.Feed(k)
    f.thread = "not started"
    return f


BTC, GOLD, SOL = "KXBTC15M-A", "KXGOLD15M-A", "KXCRYPTOLEAD15M-A-SOL"


def test_the_feed_keeps_only_15_minute_series_and_their_groups():
    f = quiet(Exchange())
    f.step(W + 60)
    assert f.series == {"KXBTC15M": "crypto", "KXGOLD15M": "metals", "KXCRYPTOLEAD15M": "coin race"}


def test_the_feed_lists_this_windows_markets_with_their_names_and_prices():
    f = quiet(Exchange())
    f.step(W + 60)
    assert set(f.markets) == {BTC, GOLD, SOL} and f.window == W                     # not the window before's
    btc, sol = f.markets[BTC], f.markets[SOL]
    assert (btc["label"], btc["group"], btc["series"], btc["strike"]) == ("BTC", "crypto", "KXBTC15M", 100.5)
    assert sol["label"] == "Race·SOL"
    assert (btc["yes_bid"], btc["yes_ask"], btc["last"], btc["bid_size"], btc["ask_size"], btc["volume"], btc["oi"]) == \
        (0.95, 0.96, 0.95, 10.0, 5.0, 123.0, 45.0)


class Late(Exchange):
    """Gold's market isn't up yet when the window is first listed."""
    SERIES = {"KXBTC15M": ["KXBTC15M-A"], "KXGOLD15M": [], "KXCRYPTOLEAD15M": ["KXCRYPTOLEAD15M-A-SOL"]}


def test_a_market_that_opens_after_the_window_is_listed_is_added_on_the_next_look():
    k = Late()
    f = quiet(k)
    f.step(W + 5)
    assert set(f.markets) == {BTC, SOL}
    k.SERIES = {**Late.SERIES, "KXGOLD15M": [GOLD]}                                 # it opens
    f.step(W + 5 + dashboard.RELIST_EVERY - 1)
    assert GOLD not in f.markets                                                    # not due yet
    f.step(W + 5 + dashboard.RELIST_EVERY)
    assert set(f.markets) == {BTC, SOL, GOLD} and f.markets[GOLD]["label"] == "GOLD"
    asked = [c[1]["series_ticker"] for c in k.calls if c[0] == "markets" and "series_ticker" in c[1]]
    assert asked[-1] == "KXGOLD15M" and asked.count("KXBTC15M") == 1               # only the series still missing one
    f.step(W + 5 + 2 * dashboard.RELIST_EVERY)
    assert k.count("markets", "series_ticker") == len(asked)                        # every series has one now: nothing to ask


def test_a_window_is_looked_at_again_only_in_its_first_minutes():
    k = Late()
    f = quiet(k)
    f.step(W + 5)
    first = k.count("markets", "series_ticker")
    f.step(W + dashboard.RELIST_FOR + 1)                                            # gold still missing, but too late to look
    assert k.count("markets", "series_ticker") == first


def test_every_markets_price_is_read_in_one_request_every_second():
    k = Exchange()
    f = quiet(k)
    for t in (60, 60.5, 61, 62):
        f.step(W + t)
    assert k.count("markets", "tickers") == 3 and f.heartbeat == W + 62      # at 60, 61 and 62: never twice in a second
    k.prices[BTC] = (0.97, 0.98)
    f.step(W + 64)
    assert (f.markets[BTC]["yes_bid"], f.markets[BTC]["yes_ask"]) == (0.97, 0.98)


def test_a_market_kalshi_sends_that_wasnt_asked_for_is_ignored():
    class Stray(Exchange):
        def markets(self, **p):
            d = super().markets(**p)
            if "tickers" in p:
                d["markets"].append(self.raw("KXSTRAY15M-Z", self.window))
            return d
    f = quiet(Stray())
    f.step(W + 60)
    assert "KXSTRAY15M-Z" not in f.markets and f.heartbeat == W + 60


def test_more_than_50_markets_are_read_50_at_a_time():
    k = Exchange()
    f = quiet(k)
    f.series, f.window = {"KXBTC15M": "crypto"}, W
    f.markets = {f"KXBTC15M-{i:03d}": {"ticker": f"KXBTC15M-{i:03d}", "series": "KXBTC15M"} for i in range(120)}
    f.due["series"], f.due["list"] = W, W + 60                                      # the window was just listed
    f.step(W + 60)
    assert [len(c[1]["tickers"].split(",")) for c in k.calls if c[0] == "markets"] == [50, 50, 20]


def test_the_price_path_is_each_minutes_closing_quote_every_20_seconds():
    k = Exchange()
    f = quiet(k)
    f.step(W + 125)
    assert f.paths[BTC] == [[1, 0.9, 0.92], [2, 0.9, 0.92]]
    assert k.calls[-1] == ("candles", tuple(sorted((BTC, GOLD, SOL))), W, W + 125)   # every market, from the open up to now
    f.step(W + 140)
    assert k.count("candles") == 1
    f.step(W + 146)
    assert k.count("candles") == 2


def test_a_new_window_is_listed_afresh():
    k = Exchange()
    f = quiet(k)
    f.step(W + 60)
    f.books[BTC] = (W + 60, {"bids": [], "asks": []})
    k.window = W + 900
    f.step(W + 905)
    assert f.window == W + 900 and set(f.markets) == {BTC, GOLD, SOL} and f.books == {}
    assert f.markets[BTC]["open"] == bot.iso(W + 900)


def test_a_window_not_listed_yet_is_asked_for_again():
    k = Exchange(window=W - 900)        # Kalshi still lists only the last window
    f = quiet(k)
    f.step(W + 2)
    assert f.window is None and f.markets == {}
    k.window = W
    f.step(W + 5)
    assert f.window == W and BTC in f.markets


def test_kalshi_down_keeps_the_last_prices_and_stops_the_heartbeat():
    k = Exchange()
    f = quiet(k)
    f.step(W + 60)
    k.down = True
    f.step(W + 62)
    f.step(W + 90)
    assert f.heartbeat == W + 60 and f.markets[BTC]["yes_bid"] == 0.95 and f.paths[BTC]
    assert f.snapshot(W + 90)["heartbeat"] == bot.iso(W + 60)


def test_no_series_list_means_no_markets_and_it_asks_again():
    k = Exchange()
    k.down = True
    f = quiet(k)
    f.step(W + 60)
    assert f.series == {} and k.count("markets") == 0
    k.down = False
    f.step(W + 61)
    assert f.series and set(f.markets) == {BTC, GOLD, SOL}


def test_the_snapshot_waits_for_the_first_prices():
    assert quiet(Exchange()).snapshot(W + 60) is None


def test_the_snapshot_is_what_the_research_tab_draws():
    k = Exchange()
    k.prices[GOLD] = (0.02, 0.03)
    f = quiet(k)
    f.step(W + 125)
    s = f.snapshot(W + 126)
    assert s["heartbeat"] == bot.iso(W + 125) and s["band"] == [bot.LO, bot.HI]
    assert [m["ticker"] for m in s["markets"]] == [BTC, GOLD, SOL]                    # crypto, metals, then Coin Race
    assert s["groups"] == ["crypto", "metals", "coin race"]
    btc, gold = s["markets"][0], s["markets"][1]
    assert (btc["favSide"], btc["favPrice"], gold["favSide"], gold["favPrice"]) == ("yes", 0.96, "no", 0.98)
    assert btc["path"] == [[1, 0.9, 0.92], [2, 0.9, 0.92]] and btc["book"] is None    # no book unless asked for
    assert f.watched == W + 126


def test_groups_it_doesnt_know_sort_last():
    f = quiet(Exchange())
    f.step(W + 60)
    f.markets["KXNEW15M-A"] = {**f.markets[BTC], "ticker": "KXNEW15M-A", "group": "weather", "label": "NEW"}
    s = f.snapshot(W + 61)
    assert s["markets"][-1]["ticker"] == "KXNEW15M-A" and s["groups"][-1] == "weather"


def test_the_book_comes_only_for_the_market_asked_for_at_most_once_a_second():
    k = Exchange()
    f = quiet(k)
    f.step(W + 60)
    s = f.snapshot(W + 60, book=BTC)
    btc = next(m for m in s["markets"] if m["ticker"] == BTC)
    assert btc["book"] == {"bids": [[0.95, 10.0], [0.94, 3.0]], "asks": [[0.96, 5.0]]}
    assert all(m["book"] is None for m in s["markets"] if m["ticker"] != BTC)
    f.snapshot(W + 60.5, book=BTC)
    assert k.count("book") == 1                                                      # within the second: no new read
    f.snapshot(W + 61, book=BTC)
    assert k.count("book") == 2


def test_a_ticker_not_in_this_window_is_never_looked_up():
    k = Exchange()
    f = quiet(k)
    f.step(W + 60)
    f.snapshot(W + 60, book="KXEVIL-1/../../x")
    assert k.count("book") == 0


def test_a_failed_book_read_keeps_the_last_good_book():
    k = Exchange()
    f = quiet(k)
    f.step(W + 60)
    good = f.book(BTC, W + 60)
    k.down = True
    assert f.book(BTC, W + 62) == good and f.book(GOLD, W + 62) is None


def test_asking_starts_one_background_reader():
    f = dashboard.Feed(Exchange())
    started = []
    f.run = lambda: started.append(1)
    f.snapshot(W)
    f.snapshot(W + 1)
    f.thread.join(timeout=5)
    assert started == [1] and f.thread.name == "kalshi-feed" and f.thread.daemon


def test_the_reader_steps_only_while_someone_is_watching_and_survives_a_bad_answer(monkeypatch, capsys):
    clock = {"t": W + 100.0}
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + s)))
    f = quiet(Exchange())
    steps = []

    def step(now):
        steps.append(now)
        if len(steps) == 2:
            raise ValueError("odd answer")
    f.step = step
    f.watched = W + 100
    f.run(passes=3)                                                                  # watched: steps each wake, one fails
    assert steps == [W + 100, W + 100.5, W + 101] and "live feed: ValueError('odd answer')" in capsys.readouterr().out
    clock["t"] = W + 100 + dashboard.WATCHED_FOR + 5
    f.run(passes=2)                                                                  # nobody watching: no step
    assert len(steps) == 3


def test_book_levels_of_nothing_is_nothing():
    assert dashboard.book_levels(None) is None


# ------------------------------------------------------------------ the live stream (Kalshi's WebSocket), on a fake socket
class FakeTimeout(Exception):
    """websocket-client's WebSocketTimeoutException: a second with nothing to read."""


class FakeSocket:
    """A Kalshi WebSocket that hands back a script, one item a recv(): a message, an exception to raise, or (once the
    script runs out) a quiet second. It keeps what it was sent."""

    def __init__(self, script=(), close_fails=False):
        self.script, self.sent, self.closed, self.close_fails = list(script), [], False, close_fails

    def send(self, text):
        self.sent.append(json.loads(text))

    def recv(self):
        item = self.script.pop(0) if self.script else FakeTimeout()
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        self.closed = True
        if self.close_fails:
            raise OSError("already gone")


def msg(kind, **body):
    return json.dumps({"type": kind, "sid": 1, "msg": body})


def tick(ticker, bid, ask):
    return msg("ticker", market_ticker=ticker, price_dollars="0.9500", yes_bid_dollars=f"{bid:.4f}", yes_ask_dollars=f"{ask:.4f}",
               volume_fp="50.00", open_interest_fp="20.00", yes_bid_size_fp="7.00", yes_ask_size_fp="9.00")


SUBSCRIBED = [msg("subscribed", channel="ticker", sid=1), msg("subscribed", channel="trade", sid=2)]


@pytest.fixture
def clock(monkeypatch):
    """dashboard's clock, by hand: sleeps move it forward and are recorded."""
    c = {"t": W + 60.0, "slept": []}

    def sleep(s):
        c["slept"].append(s)
        c["t"] += s
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: c["t"], sleep=sleep))
    monkeypatch.setattr(dashboard, "WS", types.SimpleNamespace(WebSocketTimeoutException=FakeTimeout))
    return c


def streamed(script=(), k=None, **sock):
    """A feed on the fake exchange that has listed this window and whose stream connects to a FakeSocket."""
    k = k or Exchange()
    s = FakeSocket(script, **sock)
    connects = []
    f = dashboard.Feed(k, connect=lambda: connects.append(1) or s)
    f.thread = f.stream_thread = "not started"
    f.step(W + 60)
    f.watched = W + 60
    return f, s, k, connects


def turns(f, n, at=W + 60):
    return [f.stream_step(at) for _ in range(n)]


def test_the_stream_subscribes_to_this_windows_markets_and_their_prices_replace_polling(clock):
    f, s, k, connects = streamed(SUBSCRIBED + [tick(BTC, 0.97, 0.98)])
    assert turns(f, 3) == [0, 0, 0] and connects == [1]
    assert s.sent == [{"id": 1, "cmd": "subscribe", "params": {"channels": ["ticker", "trade"], "market_tickers": sorted([BTC, GOLD, SOL])}}]
    assert f.sids == {1, 2} and f.streaming(W + 60)
    btc = f.markets[BTC]
    assert (btc["yes_bid"], btc["yes_ask"], btc["last"], btc["bid_size"], btc["ask_size"], btc["volume"], btc["oi"]) == \
        (0.97, 0.98, 0.95, 7.0, 9.0, 50.0, 20.0)
    snap = f.snapshot(W + 61)
    assert (snap["source"], snap["streamWhy"], snap["markets"][0]["favPrice"]) == ("stream", None, 0.98)
    polled = k.count("markets", "tickers")
    f.step(W + 62)
    assert k.count("markets", "tickers") == polled                                   # streaming: no price polling


def test_a_streamed_quote_only_overwrites_the_fields_it_carries(clock):
    f, s, k, _ = streamed(SUBSCRIBED + [msg("ticker", market_ticker=BTC, yes_bid_dollars="0.9100")])
    turns(f, 3)
    assert (f.markets[BTC]["yes_bid"], f.markets[BTC]["yes_ask"], f.markets[BTC]["volume"]) == (0.91, 0.96, 123.0)


def test_trades_go_on_their_markets_tape_newest_first_and_only_the_market_on_screen_gets_it(clock, monkeypatch):
    monkeypatch.setattr(dashboard, "TRADES_KEPT", 2)
    trades = [msg("trade", market_ticker=BTC, taker_side=side, yes_price_dollars="0.9600", no_price_dollars="0.0400",
                  count_fp=f"{n}.00", ts_ms=(W + 61) * 1000 + n) for side, n in (("yes", 1), ("no", 2), ("yes", 3))]
    f, s, k, _ = streamed(SUBSCRIBED + trades + [msg("trade", market_ticker=GOLD, taker_side="yes", yes_price_dollars="0.5000", count_fp="4.00")])
    turns(f, 6)
    newest = [[pytest.approx(W + 61.003), "yes", 0.96, 3.0], [pytest.approx(W + 61.002), "no", 0.04, 2.0]]
    assert isinstance(f.trades[BTC], deque) and list(f.trades[BTC]) == newest      # newest first; the oldest falls off
    assert list(f.trades[GOLD]) == [[W + 60, "yes", 0.5, 4.0]]                     # no time sent: when it arrived
    by = {m["ticker"]: m for m in f.snapshot(W + 61, book=BTC)["markets"]}
    assert by[BTC]["trades"] == newest and by[GOLD]["trades"] is None


def test_the_stream_ignores_what_isnt_for_this_window(clock):
    junk = ["not json", "[1, 2]", msg("ok"), tick("KXOTHER15M-Z", 0.5, 0.6), msg("trade", market_ticker="KXOTHER15M-Z", taker_side="yes")]
    f, s, k, _ = streamed(SUBSCRIBED + junk)
    before = dict(f.markets[BTC])
    assert turns(f, 7) == [0] * 7
    assert f.markets[BTC] == before and "KXOTHER15M-Z" not in f.markets and f.trades == {}


def test_an_error_from_kalshi_is_kept_to_show_on_the_page(clock):
    f, s, k, _ = streamed([msg("error", code=6, msg="Already subscribed"), msg("error", code=9)])
    turns(f, 1)
    assert f.stream_why == "Kalshi's stream said: Already subscribed"
    turns(f, 1)
    assert f.stream_why == "Kalshi's stream said: {'code': 9}"
    assert f.snapshot(W + 61)["streamWhy"] == "Kalshi's stream said: {'code': 9}"   # never subscribed: polling, and why


def test_a_new_window_swaps_the_subscription(clock):
    f, s, k, _ = streamed(SUBSCRIBED)
    turns(f, 2)
    f.markets = {"KXBTC15M-B": {**f.markets[BTC], "ticker": "KXBTC15M-B"}}
    turns(f, 1)
    assert s.sent[1:] == [{"id": 2, "cmd": "unsubscribe", "params": {"sids": [1, 2]}},
                          {"id": 3, "cmd": "subscribe", "params": {"channels": ["ticker", "trade"], "market_tickers": ["KXBTC15M-B"]}}]
    assert f.sids == set() and not f.streaming(W + 60)                               # until Kalshi acknowledges the new one


def test_a_quiet_second_is_fine_but_a_long_silence_reconnects_and_polls_meanwhile(clock):
    f, s, k, connects = streamed(SUBSCRIBED)
    turns(f, 2)
    assert f.stream_step(W + 60 + dashboard.STREAM_QUIET - 1) == 0                  # a quiet second: carry on
    assert f.stream_step(W + 60 + dashboard.STREAM_QUIET + 1) == dashboard.STREAM_RETRY[0]
    assert s.closed and f.ws is None and f.stream_why == "Kalshi's stream went quiet: reconnecting, polling meanwhile"
    f.stream_step(W + 60 + dashboard.STREAM_QUIET + 2)
    assert connects == [1, 1]                                                        # and connects again


def test_a_dropped_connection_reconnects_and_the_feed_polls_meanwhile(clock):
    f, s, k, connects = streamed(SUBSCRIBED + [ConnectionResetError("reset")])
    turns(f, 2)
    assert f.stream_step(W + 61) == dashboard.STREAM_RETRY[0]
    assert f.stream_why == "Kalshi's stream dropped (ConnectionResetError('reset')): reconnecting, polling meanwhile"
    assert not f.streaming(W + 61) and f.snapshot(W + 61)["source"] == "poll"
    polled = k.count("markets", "tickers")
    f.step(W + 62)
    assert k.count("markets", "tickers") == polled + 1                              # back to polling


def test_without_websocket_client_a_read_error_is_a_drop(clock, monkeypatch):
    monkeypatch.setattr(dashboard, "WS", None)
    f, s, k, _ = streamed(SUBSCRIBED + [FakeTimeout()])
    turns(f, 2)
    assert f.stream_step(W + 60) == dashboard.STREAM_RETRY[0] and f.stream_why.startswith("Kalshi's stream dropped")


def test_a_failed_connect_backs_off_and_says_why(clock):
    f, s, k, _ = streamed()
    f.connect = lambda: (_ for _ in ()).throw(dashboard.StreamDown("no API key in .env"))
    assert [f.stream_step(W + 60) for _ in range(6)] == [1, 2, 5, 10, 30, 30]
    assert f.stream_why == "no live stream (no API key in .env), polling instead" and f.ws is None
    f.connect = lambda: s
    assert f.stream_step(W + 60) == 0 and f.tries == 0                               # connected: the back-off resets


def test_nobody_watching_or_nothing_to_watch_closes_the_socket(clock):
    f, s, k, _ = streamed(SUBSCRIBED)
    turns(f, 2)
    assert f.stream_step(W + 60 + dashboard.WATCHED_FOR) == dashboard.FEED_TICK
    assert s.closed and f.ws is None and f.stream_why is None and f.sids == set()
    f2, s2, _, connects = streamed()
    f2.markets = {}
    assert f2.stream_step(W + 60) == dashboard.FEED_TICK and connects == []          # never connects with nothing listed


def test_closing_a_socket_that_is_already_broken_is_harmless(clock):
    f, s, k, _ = streamed(SUBSCRIBED, close_fails=True)
    turns(f, 2)
    f.drop("why")
    assert s.closed and f.ws is None and f.stream_why == "why"


def test_a_live_socket_keeps_the_heartbeat_fresh_even_when_prices_hold(clock):
    f, s, k, _ = streamed(SUBSCRIBED)
    turns(f, 2)
    clock["t"] = W + 75
    s.script = [msg("trade", market_ticker=BTC, taker_side="yes", yes_price_dollars="0.9600", count_fp="1.00")]
    turns(f, 1, at=W + 75)
    assert f.heartbeat == W + 60 and f.snapshot(W + 76)["heartbeat"] == bot.iso(W + 75)   # the socket spoke at W + 75


def test_the_stream_thread_takes_turns_waits_when_told_and_survives_an_error(clock, capsys):
    f, s, k, _ = streamed()
    waits = iter([0, 2])

    def step(now):
        w = next(waits, None)
        if w is None:
            raise ValueError("odd")
        return w
    f.stream_step = step
    f.stream_run(passes=3)
    assert clock["slept"] == [2, dashboard.STREAM_RETRY[0]]
    assert "live stream: ValueError('odd')" in capsys.readouterr().out
    assert f.stream_why == "live stream error (ValueError('odd')): reconnecting, polling meanwhile"


def test_asking_starts_the_stream_thread_only_when_the_feed_can_connect():
    f = dashboard.Feed(Exchange(), connect=lambda: FakeSocket())
    ran = []
    f.run, f.stream_run = (lambda: None), (lambda: ran.append(1))
    f.snapshot(W)
    f.snapshot(W + 1)
    f.stream_thread.join(timeout=5)
    assert ran == [1] and f.stream_thread.name == "kalshi-stream" and f.stream_thread.daemon
    g = dashboard.Feed(Exchange())                                                   # a test's exchange, no connect: never streams
    g.run = lambda: None
    g.snapshot(W)
    assert g.connect is None and g.stream_thread is None


def test_a_feed_on_kalshi_itself_streams_through_open_stream():
    assert dashboard.Feed().connect is dashboard.open_stream


def test_ticker_quotes_reads_the_streams_field_names():
    assert dashboard.ticker_quotes({"yes_bid_dollars": "0.4500", "yes_ask_dollars": "0.5300", "price_dollars": "0.4800",
                                    "yes_bid_size_fp": "300.00", "yes_ask_size_fp": "150.00", "volume_fp": "33896.00",
                                    "open_interest_fp": "20422.00"}) == \
        {"yes_bid": 0.45, "yes_ask": 0.53, "last": 0.48, "bid_size": 300.0, "ask_size": 150.0, "volume": 33896.0, "oi": 20422.0}
    assert set(dashboard.ticker_quotes({}).values()) == {None}


def test_open_stream_signs_the_handshake_with_the_prod_key(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ed25519
    key = ed25519.Ed25519PrivateKey.generate()
    monkeypatch.setattr(dashboard, "client", lambda env: types.SimpleNamespace(key_id="KEY-1", key=key, env=env))
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: 1_700_000_000.5))
    calls, sock = [], FakeSocket()
    sock.settimeout = lambda t: calls.append(("timeout", t))
    monkeypatch.setattr(dashboard, "WS", types.SimpleNamespace(
        WebSocketTimeoutException=FakeTimeout, create_connection=lambda url, header, timeout: calls.append((url, header, timeout)) or sock))
    assert dashboard.open_stream() is sock
    url, header, timeout = calls[0]
    assert (url, timeout, calls[1]) == ("wss://external-api-ws.kalshi.com/trade-api/ws/v2", dashboard.STREAM_TIMEOUT, ("timeout", 1))
    assert (header["KALSHI-ACCESS-KEY"], header["KALSHI-ACCESS-TIMESTAMP"]) == ("KEY-1", "1700000000500")
    key.public_key().verify(base64.b64decode(header["KALSHI-ACCESS-SIGNATURE"]), b"1700000000500GET/trade-api/ws/v2")   # raises if not


def test_open_stream_says_why_there_is_no_stream(monkeypatch):
    monkeypatch.setattr(dashboard, "WS", None)
    with pytest.raises(dashboard.StreamDown, match="websocket-client isn't installed"):
        dashboard.open_stream()
    monkeypatch.setattr(dashboard, "WS", types.SimpleNamespace())
    monkeypatch.setattr(dashboard, "client", lambda env: "no API key in .env")
    with pytest.raises(dashboard.StreamDown, match="no API key in .env"):
        dashboard.open_stream()


# ------------------------------------------------------------------ the research tab: the study, the live markets, the routes
@pytest.fixture
def lab(tmp_path, monkeypatch):
    """An empty research folder."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path))
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: NOW))
    monkeypatch.setattr(dashboard, "FEED", quiet(Exchange()))   # never Kalshi itself
    dashboard._cache.clear()
    return tmp_path


def write(lab, name, data, mtime=None):
    path = lab / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def run(final, curve=None, **more):
    return {"start": 240.0, "final": final, "ret": final / 240.0 - 1, "broke": None, "bets": 10, "wins": 9, "winRate": 0.9,
            "need": 0.95, "perBet": 1.5, "maxDD": 0.2, "worstWindow": -9.0, "worstWindowPct": -0.04, "worstDay": -20.0,
            "losingDays": 1, "days": 3,
            "byGroup": [{"key": "crypto", "n": 10}], "byBand": [], "bySeries": [], "periods": {"before": {"bets": 4}}, "exit": None,
            "curve": curve if curve is not None else [240.0] * 30, "halves": [1.0, 2.0], **more}


def backtest(**more):
    return {"t0": "2026-07-18T00:00:00+00:00", "hours": 30, "start": 240.0,
            "periods": [{"key": "before", "label": "Jul 18 – Aug 23 · untouched", "fromHour": 0, "toHour": 10}],
            "strategies": [{"id": "m8", "name": "$10 a bet", "start": 240.0}, {"id": "vfsl", "name": "$10 a bet · skip both", "variant": True},
                           {"id": "gone", "name": "not replayed"}],
            "scenarios": {"live": {"m8": run(700.0, [240.0 + i for i in range(30)]), "vfsl": run(900.0)},
                          "backtest": {"m8": run(800.0), "vfsl": run(950.0)}},
            "starts": {"aug24": {"live": {"m8": run(500.0, [None] * 12 + [240.0] * 18)}, "backtest": {"m8": run(600.0)}}},
            "edge": {"live": {"m8": {"bets": 99, "perBet": -0.5, "pnl": -14.0, "curve": list(range(30)), "periods": {}}},
                     "backtest": {"m8": {"bets": 99, "perBet": 3.6, "pnl": 40.0, "curve": list(range(30)), "periods": {}}}},
            **more}


def test_research_with_nothing_there_yet(lab):
    assert dashboard.study() == {"stamp": 0, "replay": None, "findings": None, "key": None, "calibration": None,
                                 "groups": None, "sizing": None, "floor": None, "losses": None}
    assert dashboard.research_live() == {"now": NOW, "stamp": 0, "live": None}


def test_the_replay_is_every_run_by_fills_and_start_with_its_curve_thinned(lab):
    write(lab, "strategies.json", backtest())
    r = dashboard.replay()
    assert (r["t0"], r["hours"], r["step"], r["start"]) == ("2026-07-18T00:00:00+00:00", 30, dashboard.REPLAY_STEP, 240.0)
    assert [s["id"] for s in r["strategies"]] == ["m8", "vfsl"]                 # only accounts with a run
    assert r["periods"][0]["key"] == "before"
    m8 = r["runs"]["live"]["jul18"]["m8"]
    assert m8["curve"] == [240.0 + i for i in range(30)][::dashboard.REPLAY_STEP]
    assert set(m8) == set(dashboard.RUN_STATS) | {"curve"} and "halves" not in m8   # every stat the page reads, nothing more
    assert m8["worstWindowPct"] == -0.04                                       # the worst 15 minutes, as a share of the bankroll
    assert r["runs"]["backtest"]["jul18"]["vfsl"]["final"] == 950.0
    assert r["runs"]["live"]["aug24"]["m8"]["curve"] == ([None] * 12 + [240.0] * 18)[::dashboard.REPLAY_STEP]
    assert r["runs"]["backtest"]["aug24"] == {"m8": {**{k: run(600.0).get(k) for k in dashboard.RUN_STATS}, "curve": [240.0] * 5}}


def test_each_rules_edge_comes_through_with_its_curve_thinned(lab):
    write(lab, "strategies.json", backtest())
    e = dashboard.replay()["edge"]
    assert e["live"]["m8"]["perBet"] == -0.5 and e["backtest"]["m8"]["pnl"] == 40.0
    assert e["live"]["m8"]["curve"] == list(range(30))[::dashboard.REPLAY_STEP]


def test_no_pause_runs_reach_the_page_even_from_an_older_backtest(lab):
    """The replays trade every window with no pauses: a pause block in an old strategies.json is ignored."""
    write(lab, "strategies.json", backtest(pause={"drop": 0.2, "within": 24, "rest": 12, "scenarios": {"live": {"m8": run(1.0)}}}))
    r = dashboard.replay()
    assert "paused" not in r and "pause" not in r
    assert not {"pauses", "pausedBets"} & set(dashboard.RUN_STATS)


def test_an_older_backtest_without_edge_runs_or_a_second_start(lab):
    b = backtest()
    del b["edge"], b["starts"]
    write(lab, "strategies.json", b)
    r = dashboard.replay()
    assert r["edge"] is None and r["runs"]["live"]["aug24"] == {} and r["runs"]["live"]["jul18"]["m8"]["final"] == 700.0


def test_a_dec10_start_reaches_the_page_when_the_backtest_has_one(lab):
    b = backtest()
    b["starts"]["dec10"] = {"live": {"m8": run(300.0)}, "backtest": {"m8": run(310.0)}}
    write(lab, "strategies.json", b)
    runs = dashboard.replay()["runs"]
    assert set(runs["live"]) == set(runs["backtest"]) == {"dec10", "jul18", "aug24"}
    assert runs["live"]["dec10"]["m8"]["final"] == 300.0 and runs["backtest"]["dec10"]["m8"]["curve"] == [240.0] * 5


def test_a_backtest_from_before_the_dec10_start_offers_no_such_start(lab):
    write(lab, "strategies.json", backtest())
    assert set(dashboard.replay()["runs"]["live"]) == {"jul18", "aug24"}


def test_no_replay_without_the_backtest(lab):
    assert dashboard.replay() is None
    write(lab, "strategies.json", {"scenarios": {"backtest": {}}})
    assert dashboard.replay() is None


def test_the_study_reads_every_research_file(lab):
    write(lab, "strategies.json", backtest())
    write(lab, "findings.json", {"periods": {"before": {"perBet": -5.9}}})
    write(lab, "key_stats.json", {"markets": 92588, "calibration": [{"band": 9, "price": 0.944}]})
    write(lab, "all_markets.json", {"groups": {"crypto": {}}, "calibration": {}, "rules": {}, "coLosses": {}, "spreads": {},
                                    "slip": 0.004, "coinRaceUnderdog": ["left out"]})
    write(lab, "sizing.json", [{"label": "3%", "horizon": 30}])
    s = dashboard.study()
    assert s["replay"]["runs"]["live"]["jul18"]["m8"]["final"] == 700.0
    assert s["findings"] == {"periods": {"before": {"perBet": -5.9}}} and s["key"]["markets"] == 92588
    assert s["calibration"] == [{"band": 9, "price": 0.944}]                        # from key_stats.json
    assert set(s["groups"]) == {"groups", "calibration", "rules", "coLosses", "spreads", "slip"}   # only what the page draws
    assert s["sizing"] == [{"label": "3%", "horizon": 30}]


def test_the_calibration_falls_back_to_the_older_snapshot(lab):
    write(lab, "dashboard/src/generated/dashboard.json", {"calibration": [{"label": "90–100"}], "other": 1})
    assert dashboard.study()["calibration"] == [{"label": "90–100"}]
    write(lab, "key_stats.json", {"markets": 5})                                     # key_stats without a table: still the snapshot
    assert dashboard.study()["calibration"] == [{"label": "90–100"}]


def test_a_broken_research_file_reads_as_none(lab):
    write(lab, "findings.json", "{not json")
    assert dashboard.study()["findings"] is None


def test_the_stamp_is_when_the_newest_research_file_changed(lab):
    write(lab, "findings.json", {}, mtime=1000)
    write(lab, "sizing.json", [], mtime=3000)
    write(lab, "strategies.json", {}, mtime=2000)
    write(lab, "unrelated.json", {}, mtime=9000)                                 # not one the tab reads
    assert dashboard.stamp() == 3000


# ------------------------------------------------------------------ the research routes
def test_the_study_and_live_routes(lab):
    dashboard.FEED.step(W + 60)
    write(lab, "findings.json", {"x": 1})
    with serving() as base:
        status, headers, body = fetch(base, "/api/research")
        lstatus, _, lbody = fetch(base, "/api/research/live?book=KXGOLD15M-A")
        _, _, plain = fetch(base, "/api/research/live")
    s, live_feed, no_book = json.loads(body), json.loads(lbody), json.loads(plain)
    assert status == lstatus == 200 and headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
    assert s["findings"] == {"x": 1} and "live" not in s                          # the study holds no prices ...
    books = {m["ticker"]: m["book"] for m in live_feed["live"]["markets"]}        # ... the live feed does, and the book asked for
    assert books["KXGOLD15M-A"] is not None and books["KXBTC15M-A"] is None
    assert all(m["book"] is None for m in no_book["live"]["markets"])
    assert live_feed["stamp"] == s["stamp"]


def test_the_study_is_read_again_only_when_a_research_file_changes(lab):
    write(lab, "findings.json", {"v": 1}, mtime=1000)
    with serving() as base:
        first = json.loads(fetch(base, "/api/research")[2])
        write(lab, "findings.json", {"v": 2}, mtime=1000)                         # rewritten, same time: still the cached study
        same = json.loads(fetch(base, "/api/research")[2])
        write(lab, "findings.json", {"v": 3}, mtime=2000)                         # a newer file: read again
        newer = json.loads(fetch(base, "/api/research")[2])
    assert (first["findings"], same["findings"], newer["findings"]) == ({"v": 1}, {"v": 1}, {"v": 3})
    assert newer["stamp"] == 2000


@pytest.mark.parametrize("path", ["/research.py", "/bot.py", "/.env", "/state/live-prod.db", "/research.js/../bot.py", "/api/research/x",
                                  "/research.js", "/research.css"])   # the Historical Research tab's files left with it (Oct 15)
def test_no_other_file_in_the_folder_is_served(lab, path):
    with serving() as base:
        assert fetch(base, path)[0] == 404
