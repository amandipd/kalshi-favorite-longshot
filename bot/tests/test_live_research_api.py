"""The Live Research tab's server side: GET /api/live-research, which follows the +1¢ limit experiment in the bot's own
records. From its next restart the bot's immediate-or-cancel (IOC) buy order sits 1¢ over the ask it saw (bot.LIMIT_UP):
live_research() finds the first such order and splits the buy orders into "before" and "during" it. It splits the
during orders' fills into "base" contracts, at or under the ask it saw (the old limit would have bought them too), and
"extra" ones, over it (only the new limit buys them). It says whether the extra contracts make money, with a 95% range
whose standard error is clustered by window (bets in one 15-minute window share their luck, so the window is the unit),
next to what the research predicted. It opens the ledger read-only and never changes it, even one from before the
restart that has no fills table yet.

For now the live limit is back at the ask (bot.LIMIT_UP is 0) and the +1¢ runs on paper (test_shadow_api.py), where an
empty experiment says "off" instead of "waiting": the tests of the waiting state switch the live cent on themselves.

Every ledger here is built with the CREATE TABLE statements bot.connect() runs before the restart, plus the fills table
where a test needs one, so they stay the same when bot.connect() changes. Each number is worked out by hand in the test.
Nothing here touches the network or the real research files.

    python -m pytest tests/test_live_research_api.py -q
"""
import json
import math
import os
import sqlite3

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, fetch, home, serving  # noqa: F401  (home is a fixture)

# The ledger's tables as bot.connect() makes them before the +1c restart: no fills table.
OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY, ticker TEXT UNIQUE, series TEXT, window_open REAL, close_ts REAL,
    side TEXT, price REAL, contracts REAL, cost REAL, fee REAL, placed_ts REAL,
    order_id TEXT, client_order_id TEXT, status TEXT, result TEXT, payout REAL, pnl REAL, settled_ts REAL);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT UNIQUE, series TEXT, yes_bid REAL, yes_ask REAL,
    fav_side TEXT, fav_price REAL, action TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY, ts REAL, ticker TEXT, client_order_id TEXT, request TEXT, http_status INTEGER, response TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
# ... and the table the restart adds: every fill of its orders, on the side it bought
FILLS = ("CREATE TABLE IF NOT EXISTS fills (id INTEGER PRIMARY KEY, trade_id TEXT UNIQUE, order_id TEXT, ticker TEXT,"
         " side TEXT, price REAL, count REAL, fee REAL, ts REAL)")

WAITING = "Not started: the bot sends +1¢ limits from its next restart."
TOO_EARLY = "Too early to tell: {n} of {target} orders with the +1¢ limit so far."
HELPING = "The extra cent is paying: the extra contracts made money, and their 95% range is above zero."
HURTING = "The extra cent is losing money: the extra contracts' 95% range is below zero."
NO_DIFFERENCE = "No clear difference: the extra contracts' 95% range includes zero."

ARM_KEYS = {"orders", "asked", "filled", "fillShare", "none", "partial", "full", "avgSeen", "avgPaid", "settled", "won",
            "pnl", "staked", "perTen", "se"}
GROUP_KEYS = {"orders", "contracts", "avgPrice", "fee", "breakEven", "settled", "won", "winRate", "pnl", "staked",
              "perTen", "se", "windows"}
ORDER_KEYS = {"ts", "ticker", "side", "seen", "limit", "asked", "filled", "base", "extra", "avgPaid", "result"}
EMPTY_ARM = {"orders": 0, "asked": 0, "filled": 0, "fillShare": None, "none": 0, "partial": 0, "full": 0, "avgSeen": None,
             "avgPaid": None, "settled": 0, "won": 0, "pnl": 0, "staked": 0, "perTen": None, "se": None}
EMPTY_GROUP = {"orders": 0, "contracts": 0, "avgPrice": None, "fee": 0, "breakEven": None, "settled": 0, "won": 0,
               "winRate": None, "pnl": 0, "staked": 0, "perTen": None, "se": None, "windows": 0}


@pytest.fixture(autouse=True)
def no_real_research(tmp_path_factory, monkeypatch):
    """No test reads the real research folder: each starts with an empty one, and the prediction tests fill their own."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path_factory.mktemp("research")))


# ------------------------------------------------------------------ building a ledger
def ledger(home, fills=True, name="live-prod"):
    """A mode's ledger in the test's state folder, made as the bot made it before the restart, plus the fills table the
    restart adds unless fills=False."""
    db = sqlite3.connect(str(home.dir / f"{name}.db"))
    db.executescript(OLD_SCHEMA)
    if fills:
        db.execute(FILLS)
    db.execute("INSERT INTO meta VALUES ('start', '100.0')")
    db.commit()
    return db


def trade(db, ts, ticker, seen, limit, asked, filled=0, side="yes", fills=(), bet=None, action=None):
    """One buy order as the bot records it: its decision, with the ask it saw (seen; None: no decision row), the order
    it sent with its limit on the side it buys (bot.order_body: a NO buy is an ask at 1 - limit) and Kalshi's answer,
    the order's fills [(count, price, fee)], and the bet its contracts made: bet = (window_open, status, cost, fee, pnl).
    The bet's price is what it paid, cost / filled."""
    oid = "o-" + ticker
    if seen is not None:   # a filled order logs a "bet"; one that got nothing logs a "skip" (nobody selling at that price)
        db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
                   (ts, ticker, ticker.split("-")[0], side, seen, action or ("bet" if filled else "skip"), "test"))
    body = bot.order_body(ticker, side, limit, asked)
    answer = {"order_id": oid, "fill_count": f"{filled:.2f}", "remaining_count": "0.00", "status": "executed"}
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, body["client_order_id"], json.dumps(body), 201, json.dumps(answer)))
    for i, (count, price, fee) in enumerate(fills):
        db.execute("INSERT INTO fills (trade_id, order_id, ticker, side, price, count, fee, ts) VALUES (?,?,?,?,?,?,?,?)",
                   (f"{oid}-{i}", oid, ticker, side, price, count, fee, ts + 0.5))
    if bet:
        window, status, cost, fee, pnl = bet
        settled = status != "open"
        db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts,"
                   " order_id, client_order_id, status, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (ticker, ticker.split("-")[0], window, window + 900, side, cost / filled, filled, cost, fee, ts, oid,
                    body["client_order_id"], status, pnl if settled else None, window + 960 if settled else None))


def refused(db, ts, ticker, status, response, seen=0.90, limit=0.95):
    """An order 5c over the ask it saw that Kalshi refused, never answered, or answered with something that isn't an
    order: left out of everything, so it can't start the experiment either."""
    db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
               (ts, ticker, ticker.split("-")[0], "yes", seen, "error", "order failed"))
    body = bot.order_body(ticker, "yes", limit, 10)
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, body["client_order_id"], json.dumps(body), status, response))


def cancel(db, ts, ticker):
    """A cancel the bot sent for one of its orders: the orders table holds these too, with {"cancel": order id}."""
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, bot.client_order_id(ticker), json.dumps({"cancel": "o-" + ticker}), 200,
                json.dumps({"order": {"status": "canceled"}})))


REFUSED = json.dumps({"error": {"code": "insufficient_balance", "message": "insufficient balance"}})
WA, WB, W1, W2, W3, W4 = (NOW - 900 * k for k in (6, 5, 4, 3, 2, 1))   # six 15-minute windows, oldest first
START = W1 + 480                                                       # the first +1c order: minute 8 of W1


def experiment(home, fills=True):
    """A ledger across the restart. Before it (WA, WB) each limit is the ask it saw; from W1 on it is 1c over. Around it,
    noise that must be left out of everything: cancels, refused orders, and a fill of some other order.
    fills=False: the same ledger before the fills table existed (nothing recorded which price each contract filled at)."""
    db = ledger(home, fills)
    f = (lambda *rows: rows) if fills else (lambda *rows: ())
    # before: limit == the ask it saw
    trade(db, WA + 480, "KXBTC15M-A", 0.95, 0.95, 10, 10, fills=f((10, 0.95, 0.05)), bet=(WA, "won", 9.50, 0.05, 0.45))
    trade(db, WA + 481, "KXETH15M-A", 0.93, 0.93, 10, 4, side="no", bet=(WA, "lost", 3.72, 0.03, -3.75))
    trade(db, WA + 482, "KXSOL15M-A", 0.96, 0.96, 10, 0)
    trade(db, WB + 480, "KXXRP15M-B", None, 0.97, 5, 5, bet=(WB, "open", 4.85, 0.02, None))   # no decision: no ask seen
    refused(db, WA + 483, "KXDOGE15M-A", 400, REFUSED)
    refused(db, WB + 481, "KXHYPE15M-B", None, json.dumps("network error: timed out"))
    refused(db, WB + 482, "KXBNB15M-B", 201, json.dumps("odd"))
    refused(db, WB + 483, "KXSHIB15M-B", 201, "not json")
    refused(db, WB + 484, "KXADA15M-B", 500, json.dumps({"detail": "oops"}))
    cancel(db, WB + 490, "KXXRP15M-B")
    # during: limit 1c over the ask it saw. W1 has three bets, one of them lost.
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=f((6, 0.95, 0.03), (4, 0.96, 0.02)),
          bet=(W1, "won", 9.54, 0.05, 0.41))
    trade(db, W1 + 481, "KXETH15M-1", 0.93, 0.94, 10, 5, side="no", fills=f((2, 0.93, 0.01), (3, 0.94, 0.02)),
          bet=(W1, "lost", 4.68, 0.03, -4.71))
    trade(db, W1 + 482, "KXSOL15M-1", 0.96, 0.97, 10, 10, fills=f((5, 0.96, 0.02), (5, 0.97, 0.02)),
          bet=(W1, "won", 9.65, 0.04, 0.31))
    trade(db, W2 + 480, "KXBTC15M-2", 0.97, 0.98, 8, 8, fills=f((5, 0.97, 0.01), (3, 0.98, 0.01)),
          bet=(W2, "won", 7.79, 0.02, 0.19))
    trade(db, W2 + 481, "KXSOL15M-2", 0.94, 0.95, 10, 0)                                     # got nothing
    refused(db, W2 + 482, "KXHYPE15M-2", 400, REFUSED, seen=0.94, limit=0.95)
    trade(db, W3 + 480, "KXETH15M-3", 0.92, 0.93, 10, 10, fills=f((4, 0.92, 0.02), (6, 0.93, 0.03)),
          bet=(W3, "lost", 9.26, 0.05, -9.31))
    trade(db, W3 + 481, "KXDOGE15M-3", 0.95, 0.96, 6, 6, bet=(W3, "won", 5.70, 0.03, 0.27))     # fills never recorded
    trade(db, W4 + 480, "KXXRP15M-4", 0.95, 0.96, 10, 3, fills=f((1, 0.95, 0.01), (2, 0.96, 0.01)),
          bet=(W4, "open", 2.87, 0.02, None))                                                   # not settled yet
    cancel(db, W4 + 490, "KXXRP15M-4")
    if fills:   # a fill of some other order in a market it bought: not this order's
        db.execute("INSERT INTO fills (trade_id, order_id, ticker, side, price, count, fee, ts) VALUES (?,?,?,?,?,?,?,?)",
                   ("stray", "o-elsewhere", "KXBTC15M-1", "yes", 0.99, 7, 0.05, W1 + 500))
    db.commit()
    return db


# Its two arms, by hand. Before: 4 orders (B1 full, B2 4 of 10, B3 nothing, B4 full with no decision row).
BEFORE = {"orders": 4, "asked": 35, "filled": 19, "fillShare": 19 / 35, "none": 1, "partial": 1, "full": 2,
          "avgSeen": (0.95 + 0.93 + 0.96) / 3, "avgPaid": (9.50 + 3.72 + 4.85) / (10 + 4 + 5),
          "settled": 10 + 4, "won": 10, "pnl": 0.45 - 3.75, "staked": 9.50 + 3.72,
          "perTen": 1000 * (0.45 - 3.75) / (9.50 + 3.72), "se": None}   # one settled window: no standard error
# During: 8 orders from START; the refused one and the cancel are left out.
DURING = {"orders": 8, "asked": 10 + 10 + 10 + 8 + 10 + 10 + 6 + 10, "filled": 10 + 5 + 10 + 8 + 0 + 10 + 6 + 3,
          "fillShare": 52 / 74, "none": 1, "partial": 2, "full": 5,
          "avgSeen": (0.95 + 0.93 + 0.96 + 0.97 + 0.94 + 0.92 + 0.95 + 0.95) / 8,
          "avgPaid": (9.54 + 4.68 + 9.65 + 7.79 + 9.26 + 5.70 + 2.87) / 52,
          "settled": 10 + 5 + 10 + 8 + 10 + 6, "won": 10 + 10 + 8 + 6,
          "pnl": 0.41 - 4.71 + 0.31 + 0.19 - 9.31 + 0.27, "staked": 9.54 + 4.68 + 9.65 + 7.79 + 9.26 + 5.70,
          "perTen": 1000 * (0.41 - 4.71 + 0.31 + 0.19 - 9.31 + 0.27) / (9.54 + 4.68 + 9.65 + 7.79 + 9.26 + 5.70)}
# Each settled window's (P&L, staked), for the clustered standard error.
DURING_WINDOWS = [(0.41 - 4.71 + 0.31, 9.54 + 4.68 + 9.65),   # W1: three bets
                  (0.19, 7.79),                                # W2 (its unfilled order adds nothing)
                  (-9.31 + 0.27, 9.26 + 5.70)]                 # W3; W4's bet is still open
# Its fills, per fill: won → count·(1 − price) − fee, lost → −count·price − fee.
BASE_WINDOWS = [(6 * (1 - 0.95) - 0.03 + (-2 * 0.93 - 0.01) + 5 * (1 - 0.96) - 0.02, 6 * 0.95 + 2 * 0.93 + 5 * 0.96),
                (5 * (1 - 0.97) - 0.01, 5 * 0.97),
                (-4 * 0.92 - 0.02, 4 * 0.92)]
EXTRA_WINDOWS = [(4 * (1 - 0.96) - 0.02 + (-3 * 0.94 - 0.02) + 5 * (1 - 0.97) - 0.02, 4 * 0.96 + 3 * 0.94 + 5 * 0.97),
                 (3 * (1 - 0.98) - 0.01, 3 * 0.98),
                 (-6 * 0.93 - 0.03, 6 * 0.93)]


def clustered_se(windows):
    """The standard error of ¢ per $10, clustered by window, from each settled window's (P_w, S_w): R = ΣP/ΣS and
    se = 1000·sqrt(G/(G−1)·Σ(P_w − R·S_w)²)/ΣS."""
    P, S, G = sum(p for p, _ in windows), sum(s for _, s in windows), len(windows)
    R = P / S
    return 1000 * math.sqrt(G / (G - 1) * sum((p - R * s) ** 2 for p, s in windows)) / S


def same(got, want):
    """got has every key of want: numbers within 1e-9, [min, max] pairs likewise, None still None, text equal."""
    for k, v in want.items():
        assert k in got, f"no {k!r} in {got}"
        if v is None:
            assert got[k] is None, f"{k}: {got[k]!r}, want None"
        elif isinstance(v, (list, tuple)):
            assert got[k] is not None and list(got[k]) == pytest.approx(list(v), abs=1e-9), f"{k}: {got[k]!r}, want {v!r}"
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            assert got[k] is not None and got[k] == pytest.approx(v, abs=1e-9), f"{k}: {got[k]!r}, want {v!r}"
        else:
            assert got[k] == v, f"{k}: {got[k]!r}, want {v!r}"


# ------------------------------------------------------------------ the route
def stub(monkeypatch):
    """live_research() stood in for: it says which mode it was asked for. The calls are returned."""
    calls = []
    monkeypatch.setattr(dashboard, "live_research", lambda m: calls.append(m) or {"mode": m, "stub": True}, raising=False)
    return calls


def get(base, path):
    status, headers, body = fetch(base, path)
    assert status == 200, f"{path}: HTTP {status} {body[:200]!r}"
    assert headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
    return json.loads(body)


def test_the_route_answers_for_the_first_mode(home, monkeypatch):
    for name in ("live-demo", "live-prod"):
        ledger(home, name=name).close()
    calls = stub(monkeypatch)
    with serving() as base:
        assert get(base, "/api/live-research") == {"mode": "live-prod", "stub": True}   # real money first, as /api/state
    assert calls == ["live-prod"]


def test_a_paper_ledger_takes_the_route_over_as_it_does_the_state(home, monkeypatch):
    for name in ("live-demo", "live-prod", "dry-prod"):
        ledger(home, name=name).close()
    calls = stub(monkeypatch)
    with serving() as base:
        assert get(base, "/api/live-research") == {"mode": "dry-prod", "stub": True}   # the live tabs are gone
    assert calls == ["dry-prod"]


def test_a_mode_can_be_chosen_only_from_the_modes_that_exist(home, monkeypatch):
    for name in ("live-prod", "live-demo", "paper-prod"):
        ledger(home, name=name).close()
    calls = stub(monkeypatch)
    with serving() as base:
        assert get(base, "/api/live-research?mode=live-demo")["mode"] == "live-demo"
        for bad in ("nope", "", "../../etc/passwd", "live-prod.db", "dry-prod", "paper-prod", "..%2Fstate%2Flive-prod"):
            assert get(base, f"/api/live-research?mode={bad}")["mode"] == "live-prod"   # no paths from outside
    assert set(calls) == {"live-demo", "live-prod"}


def test_with_no_records_yet_it_says_so(home, monkeypatch):
    ledger(home, name="paper-prod").close()      # a --paper account still gets no tab
    calls = stub(monkeypatch)
    with serving() as base:
        assert get(base, "/api/live-research") == {"error": "no live records yet"}
        assert get(base, "/api/live-research?mode=paper-prod") == {"error": "no live records yet"}
    assert calls == []


def test_the_route_serves_live_research_as_json(home):
    experiment(home).close()
    with serving() as base:
        served = get(base, "/api/live-research")
    assert served == json.loads(json.dumps(dashboard.live_research("live-prod"), default=str))   # the clock is frozen
    assert served["mode"] == "live-prod" and served["started"] == START


def test_the_route_is_cached_for_live_research_every_seconds_per_mode(home, monkeypatch):
    for name in ("live-prod", "live-demo"):
        ledger(home, name=name).close()
    assert dashboard.LIVE_RESEARCH_EVERY == 2                           # the tab's 2-second poll
    every = dashboard.LIVE_RESEARCH_EVERY
    calls = stub(monkeypatch)
    with serving() as base:
        get(base, "/api/live-research")
        get(base, "/api/live-research")
        assert calls == ["live-prod"]
        home.clock[0] = NOW + every - 0.5
        get(base, "/api/live-research")
        assert calls == ["live-prod"]
        get(base, "/api/live-research?mode=live-demo")                  # each mode is its own entry
        assert calls == ["live-prod", "live-demo"]
        home.clock[0] = NOW + every + 0.5
        get(base, "/api/live-research")
        assert calls == ["live-prod", "live-demo", "live-prod"]
    assert ("liveresearch", "live-prod") in dashboard._cache and ("liveresearch", "live-demo") in dashboard._cache


def test_the_cache_time_is_read_from_the_constant(home, monkeypatch):
    ledger(home).close()
    calls = stub(monkeypatch)
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_EVERY", 60, raising=False)
    with serving() as base:
        get(base, "/api/live-research")
        home.clock[0] = NOW + 30
        get(base, "/api/live-research")
        assert calls == ["live-prod"]
        home.clock[0] = NOW + 61
        get(base, "/api/live-research")
        assert calls == ["live-prod", "live-prod"]


def test_the_live_research_tabs_files_are_served(home, monkeypatch, tmp_path):
    assert dashboard.ASSETS.get("/live_research.js") == ("live_research.js", "text/javascript; charset=utf-8")
    assert dashboard.ASSETS.get("/live_research.css") == ("live_research.css", "text/css; charset=utf-8")
    code = tmp_path / "code"                     # stand-in files: the real ones belong to another change
    code.mkdir()
    (code / "live_research.js").write_bytes(b"window.liveResearchView = () => {};\n")
    (code / "live_research.css").write_bytes(b"#liveresearch .lr-note { color: gray; }\n")
    monkeypatch.setattr(dashboard, "STATIC", str(code))
    with serving() as base:
        for path, kind in (("/live_research.js", "text/javascript; charset=utf-8"), ("/live_research.css", "text/css; charset=utf-8")):
            status, headers, body = fetch(base, path)
            assert status == 200 and headers["Content-Type"] == kind and headers["Cache-Control"] == "no-store"
            assert body == (code / path[1:]).read_bytes()


def test_the_limits_say_how_far_over_the_ask_the_bot_bids(home, monkeypatch):
    """The page's "How it trades" reads the cent from the bot, never its own copy."""
    ledger(home).close()
    assert bot.LIMIT_UP == 0.01                   # live since Oct 20, 2026, after the +1¢ ran on paper (bot.SHADOW_UP)
    assert dashboard.state("live-prod")["limits"]["limitUp"] == bot.LIMIT_UP
    assert dashboard.live_research("live-prod")["limitUp"] == bot.LIMIT_UP
    monkeypatch.setattr(bot, "LIMIT_UP", 0.02)
    assert dashboard.state("live-prod")["limits"]["limitUp"] == 0.02
    assert dashboard.live_research("live-prod")["limitUp"] == 0.02


# ------------------------------------------------------------------ read only
@pytest.mark.parametrize("fills", [True, False], ids=["with-fills-table", "before-the-restart"])
def test_reading_never_changes_the_ledger(home, fills):
    experiment(home, fills).close()
    path = home.dir / "live-prod.db"
    before, stamp, files = path.read_bytes(), os.stat(path).st_mtime_ns, sorted(os.listdir(home.dir))
    r = dashboard.live_research("live-prod")
    assert r["arms"]["during"]["orders"] == 8                              # it did read it
    assert path.read_bytes() == before and os.stat(path).st_mtime_ns == stamp
    assert sorted(os.listdir(home.dir)) == files                           # nothing new beside it
    assert not [n for n in os.listdir(home.dir) if n.endswith(("-journal", "-wal", "-shm"))]


def test_the_ledger_is_opened_read_only(home, monkeypatch):
    experiment(home).close()
    real, calls = sqlite3.connect, []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", spy)
    dashboard.live_research("live-prod")
    assert calls, "live_research() never opened the ledger"
    for args, kwargs in calls:   # file:///.../live-prod.db?mode=ro, as a URI: SQLite can't write through it
        assert kwargs.get("uri") is True and str(args[0]).startswith("file:"), (args, kwargs)
        assert str(args[0]).endswith("live-prod.db?mode=ro"), (args, kwargs)


def test_a_ledger_from_before_the_restart_works_without_a_fills_table(home):
    """The fills table comes with the restart: until then every filled +1c order's split is unknown."""
    experiment(home, fills=False)
    r = dashboard.live_research("live-prod")
    assert r["fillsRecorded"] is False and r["started"] == START
    same(r["arms"]["before"], BEFORE)
    same(r["arms"]["during"], DURING)
    assert r["split"]["unknown"] == {"orders": 7, "contracts": 52}         # every filled during order
    same(r["split"]["base"], EMPTY_GROUP)
    same(r["split"]["extra"], EMPTY_GROUP)
    assert {o["ticker"]: (o["base"], o["extra"]) for o in r["orders"]} == {
        "KXBTC15M-1": (None, None), "KXETH15M-1": (None, None), "KXSOL15M-1": (None, None), "KXBTC15M-2": (None, None),
        "KXSOL15M-2": (0, 0), "KXETH15M-3": (None, None), "KXDOGE15M-3": (None, None), "KXXRP15M-4": (None, None)}
    assert r["verdict"]["state"] == "too-early"


# ------------------------------------------------------------------ the reply
def test_the_reply_has_every_part(home):
    experiment(home)
    r = dashboard.live_research("live-prod")
    assert {"mode", "now", "limitUp", "target", "started", "fillsRecorded", "arms", "split", "verdict", "predictions",
            "orders"} <= set(r)
    assert (r["mode"], r["now"], r["target"], r["started"], r["fillsRecorded"]) == ("live-prod", NOW, 1000, START, True)
    assert set(r["arms"]) == {"before", "during"} and {"base", "extra", "unknown"} <= set(r["split"])
    for arm in r["arms"].values():
        assert ARM_KEYS <= set(arm)
    for group in ("base", "extra"):
        assert GROUP_KEYS <= set(r["split"][group])
    assert {"orders", "contracts"} <= set(r["split"]["unknown"])
    assert {"state", "text", "orders", "target"} <= set(r["verdict"])
    assert set(r["predictions"]) == {"history", "live"}
    assert all(ORDER_KEYS <= set(o) for o in r["orders"])
    json.dumps(r, allow_nan=False)                                         # plain JSON: no NaN or infinity


def test_a_ledger_with_no_orders_yet(home, monkeypatch):
    monkeypatch.setattr(bot, "LIMIT_UP", 0.01)    # the live cent switched on (at 0 it's "off": test_shadow_api.py)
    ledger(home).close()
    r = dashboard.live_research("live-prod")
    assert r["started"] is None and r["orders"] == []
    same(r["arms"]["before"], EMPTY_ARM)
    same(r["arms"]["during"], EMPTY_ARM)
    same(r["split"]["base"], EMPTY_GROUP)
    same(r["split"]["extra"], EMPTY_GROUP)
    assert r["split"]["unknown"] == {"orders": 0, "contracts": 0}
    assert r["verdict"] == {"state": "waiting", "text": WAITING, "orders": 0, "target": 1000}


# ------------------------------------------------------------------ which orders count
def test_cancels_and_refused_orders_are_left_out_of_everything(home):
    db = ledger(home)
    # each over the ask it saw and before the real +1c order: counted, any of them would start the experiment early
    refused(db, NOW - 4000, "KXETH15M-1", 400, REFUSED)
    refused(db, NOW - 3900, "KXSOL15M-1", None, json.dumps("network error: timed out"))     # no answer from Kalshi
    refused(db, NOW - 3800, "KXXRP15M-1", 201, json.dumps(["not", "an", "order"]))          # an answer that isn't a dict
    refused(db, NOW - 3700, "KXDOGE15M-1", 201, "not json")
    refused(db, NOW - 3600, "KXBNB15M-1", 503, json.dumps({"error": "busy"}))
    refused(db, NOW - 3500, "KXADA15M-1", 199, json.dumps({"order_id": "x", "fill_count": "10.00"}))   # not a 2xx
    trade(db, NOW - 3000, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(10, 0.95, 0.05)], bet=(NOW - 3480, "won", 9.50, 0.05, 0.45))
    cancel(db, NOW - 2900, "KXBTC15M-1")
    refused(db, NOW - 2000, "KXHYPE15M-1", 400, REFUSED)                                     # after it: not a during order
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] == NOW - 3000
    same(r["arms"]["before"], EMPTY_ARM)
    same(r["arms"]["during"], {"orders": 1, "asked": 10, "filled": 10, "none": 0, "partial": 0, "full": 1})
    assert [o["ticker"] for o in r["orders"]] == ["KXBTC15M-1"]


# ------------------------------------------------------------------ when the experiment started
def test_it_starts_at_the_first_yes_order_over_the_ask_it_saw(home):
    db = ledger(home)
    trade(db, NOW - 5000, "KXBTC15M-1", 0.95, 0.95, 10)          # at the ask it saw: the old limit
    trade(db, NOW - 4000, "KXETH15M-1", None, 0.99, 10)          # no decision row: no ask to compare with
    trade(db, NOW - 3000, "KXSOL15M-1", 0.95, 0.96, 10)          # 1c over: it starts here
    trade(db, NOW - 2000, "KXXRP15M-1", 0.999, 0.999, 10)        # at the 99.9c cap the limit is the ask, but it's after the start
    trade(db, NOW - 1000, "KXDOGE15M-1", 0.92, 0.93, 10)
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] == NOW - 3000
    assert r["arms"]["before"]["orders"] == 2 and r["arms"]["during"]["orders"] == 3
    assert [o["ticker"] for o in r["orders"]] == ["KXDOGE15M-1", "KXXRP15M-1", "KXSOL15M-1"]


def test_it_starts_at_the_first_no_order_over_the_ask_it_saw(home):
    """A NO buy is an ask selling YES: its limit on the NO side is 1 minus the YES price it sends."""
    db = ledger(home)
    trade(db, NOW - 5000, "KXETH15M-1", 0.93, 0.93, 10, side="no")   # an ask at 0.07: NO at 93c, the ask it saw
    trade(db, NOW - 4000, "KXSOL15M-1", 0.96, 0.96, 10, side="no")   # an ask at 0.04
    trade(db, NOW - 3000, "KXBTC15M-1", 0.93, 0.94, 10, side="no")   # an ask at 0.06: NO at 94c, 1c over
    trade(db, NOW - 2000, "KXXRP15M-1", 0.95, 0.96, 10, side="no")
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] == NOW - 3000
    assert r["arms"]["before"]["orders"] == 2 and r["arms"]["during"]["orders"] == 2
    first = r["orders"][-1]
    same(first, {"ticker": "KXBTC15M-1", "side": "no", "seen": 0.93, "limit": 0.94})


def test_a_first_plus_one_cent_order_that_got_nothing_still_starts_it(home):
    """The ask it saw is the decision's price whatever the decision says: an order that filled nothing logs a skip."""
    db = ledger(home)
    trade(db, NOW - 5000, "KXBTC15M-1", 0.95, 0.95, 10, 10, bet=(NOW - 5480, "won", 9.50, 0.05, 0.45))
    trade(db, NOW - 3000, "KXETH15M-1", 0.95, 0.96, 10, 0)           # its decision is a "skip": nobody selling
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] == NOW - 3000
    same(r["orders"][0], {"ticker": "KXETH15M-1", "seen": 0.95, "limit": 0.96, "filled": 0, "result": None})


def test_before_any_plus_one_cent_order_it_is_waiting(home, monkeypatch):
    monkeypatch.setattr(bot, "LIMIT_UP", 0.01)    # the live cent switched on (at 0 it's "off": test_shadow_api.py)
    db = ledger(home)
    trade(db, NOW - 5000, "KXBTC15M-1", 0.95, 0.95, 10, 10, fills=[(10, 0.95, 0.05)], bet=(NOW - 5480, "won", 9.50, 0.05, 0.45))
    trade(db, NOW - 4000, "KXETH15M-1", 0.93, 0.93, 10, 4, side="no", bet=(NOW - 4480, "lost", 3.72, 0.03, -3.75))
    trade(db, NOW - 3000, "KXSOL15M-1", 0.96, 0.96, 10)
    trade(db, NOW - 2000, "KXXRP15M-1", None, 0.97, 10)              # no ask seen: can't be over it
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["started"] is None
    assert r["verdict"] == {"state": "waiting", "text": WAITING, "orders": 0, "target": 1000}
    same(r["arms"]["before"], {"orders": 4, "asked": 40, "filled": 14, "none": 2, "partial": 1, "full": 1})
    same(r["arms"]["during"], EMPTY_ARM)
    assert r["orders"] == []
    same(r["split"]["base"], EMPTY_GROUP)                                # the before order's fill isn't in the split
    same(r["split"]["extra"], EMPTY_GROUP)
    assert r["split"]["unknown"] == {"orders": 0, "contracts": 0}


# ------------------------------------------------------------------ the two arms
def test_the_before_arm_by_hand(home):
    experiment(home)
    same(dashboard.live_research("live-prod")["arms"]["before"], BEFORE)


def test_the_during_arm_by_hand(home):
    experiment(home)
    same(dashboard.live_research("live-prod")["arms"]["during"], DURING)


def test_the_standard_error_is_clustered_by_window(home):
    """Several bets in one window count as one draw of luck: the residuals are summed per window, then squared."""
    experiment(home)
    r = dashboard.live_research("live-prod")
    assert clustered_se(DURING_WINDOWS) == pytest.approx(158.36029427380655, abs=1e-6)   # the hand arithmetic, checked once
    assert clustered_se(BASE_WINDOWS) == pytest.approx(202.90924736278575, abs=1e-6)
    assert clustered_se(EXTRA_WINDOWS) == pytest.approx(253.24373788434386, abs=1e-6)
    assert r["arms"]["during"]["se"] == pytest.approx(clustered_se(DURING_WINDOWS), abs=1e-9)
    assert r["split"]["base"]["se"] == pytest.approx(clustered_se(BASE_WINDOWS), abs=1e-9)
    assert r["split"]["extra"]["se"] == pytest.approx(clustered_se(EXTRA_WINDOWS), abs=1e-9)


def test_one_settled_window_has_no_standard_error(home):
    db = ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.0), (4, 0.96, 0.0)], bet=(W1, "won", 9.54, 0.0, 0.46))
    trade(db, W1 + 481, "KXETH15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.0), (4, 0.96, 0.0)], bet=(W1, "lost", 9.54, 0.0, -9.54))
    trade(db, W2 + 480, "KXSOL15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.0), (4, 0.96, 0.0)], bet=(W2, "open", 9.54, 0.0, None))
    db.commit()
    r = dashboard.live_research("live-prod")
    during, extra = r["arms"]["during"], r["split"]["extra"]
    assert during["perTen"] == pytest.approx(1000 * (0.46 - 9.54) / (2 * 9.54)) and during["se"] is None   # W2 isn't settled
    assert extra["windows"] == 1 and extra["perTen"] is not None and extra["se"] is None


# ------------------------------------------------------------------ what the extra cent bought
def test_fills_split_into_base_and_extra_at_the_ask_it_saw(home):
    experiment(home)
    split = dashboard.live_research("live-prod")["split"]
    base_cost = 6 * 0.95 + 2 * 0.93 + 5 * 0.96 + 5 * 0.97 + 4 * 0.92 + 1 * 0.95
    extra_cost = 4 * 0.96 + 3 * 0.94 + 5 * 0.97 + 3 * 0.98 + 6 * 0.93 + 2 * 0.96
    base_fee, extra_fee = 0.03 + 0.01 + 0.02 + 0.01 + 0.02 + 0.01, 0.02 + 0.02 + 0.02 + 0.01 + 0.03 + 0.01
    same(split["base"], {"orders": 6, "contracts": 23, "avgPrice": base_cost / 23, "fee": base_fee,
                         "breakEven": base_cost / 23 + base_fee / 23, "settled": 22, "won": 6 + 5 + 5,
                         "winRate": 16 / 22, "windows": 3})
    same(split["extra"], {"orders": 6, "contracts": 23, "avgPrice": extra_cost / 23, "fee": extra_fee,
                          "breakEven": extra_cost / 23 + extra_fee / 23, "settled": 21, "won": 4 + 5 + 3,
                          "winRate": 12 / 21, "windows": 3})
    assert split["unknown"] == {"orders": 1, "contracts": 6}            # KXDOGE15M-3: filled, no fill rows


def test_each_fills_pnl_is_its_win_or_loss_less_its_fee(home):
    experiment(home)
    split = dashboard.live_research("live-prod")["split"]
    for group, windows in (("base", BASE_WINDOWS), ("extra", EXTRA_WINDOWS)):
        pnl, staked = sum(p for p, _ in windows), sum(s for _, s in windows)
        same(split[group], {"pnl": pnl, "staked": staked, "perTen": 1000 * pnl / staked})
    assert split["base"]["pnl"] == pytest.approx(-4.98) and split["extra"]["pnl"] == pytest.approx(-8.13)
    # the two groups add up to the settled bets they came from (the unknown order aside)
    assert split["base"]["pnl"] + split["extra"]["pnl"] == pytest.approx(0.41 - 4.71 + 0.31 + 0.19 - 9.31)


def test_a_fill_at_exactly_the_ask_it_saw_is_base(home):
    db = ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.93, 0.94, 12, 12, fills=[
        (3, 0.93, 0.0),              # exactly the ask it saw
        (2, 1 - 0.07, 0.0),          # 0.9299999999999999
        (2, 0.93 + 1e-10, 0.0),      # float noise over it, inside 1e-9
        (1, 0.9301, 0.0),            # a hundredth of a cent over it: the old limit wouldn't have bought it
        (4, 0.94, 0.0)], bet=(W1, "open", 3 * 0.93 + 2 * 0.93 + 2 * 0.93 + 0.9301 + 4 * 0.94, 0.0, None))
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["split"]["base"]["contracts"] == 7 and r["split"]["extra"]["contracts"] == 5
    same(r["orders"][0], {"base": 7, "extra": 5})


def test_unsettled_fills_count_in_contracts_price_and_fee_only(home):
    db = ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.03), (4, 0.96, 0.02)], bet=(W1, "won", 9.54, 0.05, 0.41))
    trade(db, W2 + 480, "KXETH15M-2", 0.95, 0.96, 10, 3, fills=[(1, 0.95, 0.01), (2, 0.96, 0.01)], bet=(W2, "open", 2.87, 0.02, None))
    db.commit()
    split = dashboard.live_research("live-prod")["split"]
    same(split["base"], {"orders": 2, "contracts": 7, "avgPrice": (6 * 0.95 + 0.95) / 7, "fee": 0.04,
                         "breakEven": (6 * 0.95 + 0.95) / 7 + 0.04 / 7,
                         "settled": 6, "won": 6, "winRate": 1.0, "pnl": 6 * 0.05 - 0.03, "staked": 6 * 0.95,
                         "perTen": 1000 * (6 * 0.05 - 0.03) / (6 * 0.95), "windows": 1, "se": None})
    same(split["extra"], {"orders": 2, "contracts": 6, "avgPrice": 0.96, "fee": 0.03, "breakEven": 0.96 + 0.03 / 6,
                          "settled": 4, "won": 4, "pnl": 4 * 0.04 - 0.02, "staked": 4 * 0.96, "windows": 1})


def test_only_unsettled_fills_have_no_win_rate_or_return(home):
    db = ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(6, 0.95, 0.03), (4, 0.96, 0.02)], bet=(W1, "open", 9.54, 0.05, None))
    db.commit()
    extra = dashboard.live_research("live-prod")["split"]["extra"]
    same(extra, {"orders": 1, "contracts": 4, "avgPrice": 0.96, "fee": 0.02, "breakEven": 0.96 + 0.02 / 4, "settled": 0,
                 "won": 0, "winRate": None, "pnl": 0, "staked": 0, "perTen": None, "se": None, "windows": 0})


def test_a_filled_order_with_no_fill_rows_is_unknown(home):
    db = ledger(home)
    trade(db, W1 + 480, "KXBTC15M-1", 0.95, 0.96, 10, 10, fills=[(10, 0.96, 0.05)], bet=(W1, "won", 9.60, 0.05, 0.35))
    trade(db, W1 + 481, "KXETH15M-1", 0.95, 0.96, 8, 6, bet=(W1, "won", 5.73, 0.03, 0.24))      # no fills recorded
    trade(db, W1 + 482, "KXSOL15M-1", 0.95, 0.96, 10, 0)                                          # nothing filled: not unknown
    db.commit()
    r = dashboard.live_research("live-prod")
    assert r["fillsRecorded"] is True
    assert r["split"]["unknown"] == {"orders": 1, "contracts": 6}
    assert r["split"]["extra"]["contracts"] == 10 and r["split"]["base"]["contracts"] == 0
    rows = {o["ticker"]: o for o in r["orders"]}
    assert (rows["KXETH15M-1"]["base"], rows["KXETH15M-1"]["extra"]) == (None, None)
    assert (rows["KXSOL15M-1"]["base"], rows["KXSOL15M-1"]["extra"]) == (0, 0)


def test_orders_before_the_experiment_never_enter_the_split(home):
    experiment(home)
    split = dashboard.live_research("live-prod")["split"]
    # KXBTC15M-A's 10 contracts at 95c before the start, and the before orders with no fill rows, stay out
    assert split["base"]["orders"] == 6 and split["base"]["contracts"] == 23
    assert split["unknown"] == {"orders": 1, "contracts": 6}
    # ... and so does the stray fill of another order in KXBTC15M-1 (7 at 99c)
    assert split["extra"]["contracts"] == 23 and split["extra"]["avgPrice"] < 0.96


# ------------------------------------------------------------------ the verdict
def raised(db, ts, ticker, window, base, extra, status, seen=0.95):
    """A +1c order that filled `base` contracts at the ask it saw and `extra` a cent over it, without fees, and its bet."""
    over, n = round(seen + 0.01, 4), base + extra
    cost = base * seen + extra * over
    pnl = n - cost if status == "won" else -cost if status == "lost" else None
    fills = [f for f in ((base, seen, 0.0), (extra, over, 0.0)) if f[0]]
    trade(db, ts, ticker, seen, over, n, n, fills=fills, bet=(window, status, cost, 0.0, pnl))


def test_too_early_below_the_target(home):
    experiment(home)
    assert dashboard.LIVE_RESEARCH_TARGET == 1000
    v = dashboard.live_research("live-prod")["verdict"]
    assert v == {"state": "too-early", "text": TOO_EARLY.format(n=8, target=1000), "orders": 8, "target": 1000}
    assert v["text"] == "Too early to tell: 8 of 1000 orders with the +1¢ limit so far."


def test_too_early_one_order_short_of_a_small_target(home, monkeypatch):
    experiment(home)
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 9, raising=False)
    r = dashboard.live_research("live-prod")
    assert r["target"] == 9
    assert r["verdict"] == {"state": "too-early", "text": TOO_EARLY.format(n=8, target=9), "orders": 8, "target": 9}


def test_too_early_without_a_standard_error_for_the_extra_contracts(home, monkeypatch):
    db = ledger(home)
    raised(db, W1 + 480, "KXBTC15M-1", W1, 5, 5, "won")
    raised(db, W2 + 480, "KXBTC15M-2", W2, 5, 5, "open")              # one settled window: no standard error yet
    db.commit()
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 2, raising=False)
    r = dashboard.live_research("live-prod")
    assert r["split"]["extra"]["se"] is None
    assert r["verdict"] == {"state": "too-early", "text": TOO_EARLY.format(n=2, target=2), "orders": 2, "target": 2}


def test_no_difference_when_the_range_includes_zero(home, monkeypatch):
    experiment(home)
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 8, raising=False)   # reached exactly: enough
    r = dashboard.live_research("live-prod")
    extra = r["split"]["extra"]
    lo, hi = extra["perTen"] - 1.96 * extra["se"], extra["perTen"] + 1.96 * extra["se"]
    assert lo < 0 < hi                                                  # about −902 to +90 ¢ per $10
    assert r["verdict"] == {"state": "no-difference", "text": NO_DIFFERENCE, "orders": 8, "target": 8}


def test_helping_when_the_whole_range_is_above_zero(home, monkeypatch):
    db = ledger(home)
    raised(db, W1 + 480, "KXBTC15M-1", W1, 5, 5, "won")
    raised(db, W2 + 480, "KXBTC15M-2", W2, 5, 5, "won")
    raised(db, W3 + 480, "KXBTC15M-3", W3, 0, 4, "won", seen=0.96)
    db.commit()
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 3, raising=False)
    r = dashboard.live_research("live-prod")
    windows = [(5 * 0.04, 5 * 0.96), (5 * 0.04, 5 * 0.96), (4 * 0.03, 4 * 0.97)]
    extra = r["split"]["extra"]
    assert extra["perTen"] == pytest.approx(1000 * 0.52 / 13.48) and extra["se"] == pytest.approx(clustered_se(windows), abs=1e-9)
    assert extra["perTen"] - 1.96 * extra["se"] > 0
    assert r["verdict"] == {"state": "helping", "text": HELPING, "orders": 3, "target": 3}


def test_hurting_when_the_whole_range_is_below_zero(home, monkeypatch):
    db = ledger(home)
    raised(db, W1 + 480, "KXBTC15M-1", W1, 0, 5, "lost")
    raised(db, W1 + 481, "KXETH15M-1", W1, 10, 0, "won")               # base contracts doing well don't change the verdict
    raised(db, W2 + 480, "KXBTC15M-2", W2, 0, 5, "lost")
    raised(db, W3 + 480, "KXBTC15M-3", W3, 0, 5, "lost")
    raised(db, W4 + 480, "KXBTC15M-4", W4, 0, 5, "won")
    db.commit()
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 5, raising=False)
    r = dashboard.live_research("live-prod")
    windows = [(-4.8, 4.8), (-4.8, 4.8), (-4.8, 4.8), (5 * 0.04, 4.8)]
    extra = r["split"]["extra"]
    assert extra["perTen"] == pytest.approx(1000 * -14.2 / 19.2) and extra["se"] == pytest.approx(clustered_se(windows), abs=1e-9)
    assert extra["perTen"] + 1.96 * extra["se"] < 0                     # about −740 ± 510
    assert r["split"]["base"]["perTen"] > 0
    assert r["verdict"] == {"state": "hurting", "text": HURTING, "orders": 5, "target": 5}


# ------------------------------------------------------------------ the predictions beside it
HIST_ROWS = [
    {"size": 10.0, "window": 30, "raise": 0.0, "orders": 35793.0, "filledAny": 0.68, "filledContracts": 0.53,
     "avgPaid": 0.951, "perTen": 3.8, "pnl": 699.4, "pre": 2.5, "post": 4.9},                 # another bet size: left out
    {"size": 10.0, "window": 30, "raise": 0.01, "filledContracts": 0.99, "perTen": 99.0, "extra": {"perTen": 99.0}},
    {"size": 30.0, "window": 30, "raise": 0.0, "filledContracts": 0.43, "perTen": 2.2},
    {"size": 30.0, "window": 10, "raise": 0.0, "filledContracts": 0.43, "perTen": 2.2},       # the window doesn't matter at 0
    {"size": 30.0, "window": 30, "raise": 0.005, "filledContracts": 0.55, "perTen": 4.0, "extra": {"perTen": 8.0}},
    {"size": 30.0, "window": 30, "raise": 0.01, "orders": 14927.0, "filledContracts": 0.73, "perTen": 6.4,
     "extra": {"orders": 14927.0, "contracts": 337298.41, "avgPrice": 0.952, "won": 0.967, "perTen": 12.3, "pnl": 3948.57,
               "pre": 8.3, "post": 14.2}},
    {"size": 30.0, "window": 10, "raise": 0.01, "filledContracts": 0.68, "perTen": 5.6, "extra": {"perTen": 11.6}},
    {"size": 30.0, "window": 2, "raise": 0.01, "filledContracts": 0.60, "perTen": 4.3, "extra": {"perTen": 9.6}},
    {"size": 30.0, "window": 30, "raise": 0.02, "filledContracts": 0.80, "perTen": 6.8, "extra": {"perTen": 12.9}},
]
HIST_FILE = {"bets": 1234, "send": {}, "depth": {}, "fresh": {}, "quiet": {}, "rows": HIST_ROWS}


def block(orders, contracts, pnl, se, per, win):
    return {"orders": orders, "orders_won": orders - 1, "contracts": contracts, "contracts_won": contracts * win,
            "vwap": 0.948, "fees": 8.06, "pnl": pnl, "pnl_se": se, "pnl_per_contract_cents": per, "contract_win_rate": win,
            "ran_past_new_limit": 11, "tape_contracts_in_band": 1000.0, "by_fill_state": {}}


LIVE_FILE = {
    "generated": "2026-10-11T21:17:00Z", "prices": {}, "fee": {},
    "stats": {"orders_sent": 400, "accepted": 398, "rejected": 2, "asked": 9000.0, "filled": 4909.5, "fill_share": 0.5455,
              "full": 100, "partial": 150, "none": 148},
    "what_if_limit": [
        {"bump_cents": 0.5, "30s": block(150, 1500.0, -5.0, 30.0, -0.3, 0.95), "5s": block(1, 1.0, 1.0, 1.0, 1.0, 0.5),
         "model": block(2, 2.0, 2.0, 2.0, 2.0, 0.5)},
        {"bump_cents": 1.0, "30s": block(205, 2382.98, -25.12, 43.16, -1.05, 0.9413),
         "5s": block(160, 1685.93, -17.63, 36.55, -0.95, 0.9412), "model": block(177, 2196.4, 10.97, 38.55, 0.5, 0.9631)},
        {"bump_cents": 2.0, "30s": block(300, 3000.0, -40.0, 50.0, -1.3, 0.94), "5s": block(3, 3.0, 3.0, 3.0, 3.0, 0.5),
         "model": block(4, 4.0, 4.0, 4.0, 4.0, 0.5)},
    ],
    "orders": [],
}


def research_files(monkeypatch, root, hist=HIST_FILE, live=LIVE_FILE):
    """A research folder with the two lab files the predictions come from; returns its lab folder."""
    lab = root / "lab"
    (lab / "live_fills").mkdir(parents=True)
    (lab / "fills.json").write_text(json.dumps(hist), encoding="utf-8")
    (lab / "live_fills" / "live_fills.json").write_text(json.dumps(live), encoding="utf-8")
    monkeypatch.setattr(dashboard, "RESEARCH", str(root))
    return lab


def test_the_predictions_from_history_and_from_the_live_fills(home, monkeypatch, tmp_path):
    ledger(home).close()
    research_files(monkeypatch, tmp_path / "study")
    p = dashboard.live_research("live-prod")["predictions"]
    # the backtest at $30 a bet: before = no raise; during = raise 1c, the range over its send windows
    same(p["history"], {"source": "research/kalshi_15min/lab/fills.json", "size": 30, "fillBefore": 0.43,
                        "fillDuring": [0.60, 0.73], "perTenBefore": 2.2, "perTenDuring": [4.3, 6.4],
                        "extraPerTen": [9.6, 12.3]})
    # the bot's own orders replayed against the tape: 1c more, contracts that would have filled within 30 s
    same(p["live"], {"fillBefore": 0.5455, "orders": 205, "contracts": 2382.98, "pnl": -25.12, "pnlSe": 43.16,
                     "perContractCents": -1.05, "winRate": 0.9413})
    assert p["live"]["source"].replace("\\", "/").endswith("lab/live_fills/live_fills.json")


def test_without_the_research_files_there_are_no_predictions(home):
    ledger(home).close()                         # the research folder is empty (no_real_research)
    assert dashboard.live_research("live-prod")["predictions"] == {"history": None, "live": None}


def without(d, *path):
    """A deep copy of d with the key at the end of path removed."""
    d = json.loads(json.dumps(d))
    *head, last = path
    inner = d
    for k in head:
        inner = inner[k]
    del inner[last]
    return d


BREAKS = {
    "no fills.json": ("history", lambda lab: (lab / "fills.json").unlink()),
    "fills.json unreadable": ("history", lambda lab: (lab / "fills.json").write_text("{not json", encoding="utf-8")),
    "fills.json without rows": ("history", lambda lab: (lab / "fills.json").write_text(
        json.dumps(without(HIST_FILE, "rows")), encoding="utf-8")),
    "no live_fills.json": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").unlink()),
    "live_fills.json unreadable": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text("[1, 2", encoding="utf-8")),
    "no stats": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps(without(LIVE_FILE, "stats")), encoding="utf-8")),
    "no fill_share": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps(without(LIVE_FILE, "stats", "fill_share")), encoding="utf-8")),
    "no what_if_limit": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps(without(LIVE_FILE, "what_if_limit")), encoding="utf-8")),
    "no 1c entry": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps({**LIVE_FILE, "what_if_limit": [LIVE_FILE["what_if_limit"][0], LIVE_FILE["what_if_limit"][2]]}),
        encoding="utf-8")),
    "1c entry without 30s": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps(without(LIVE_FILE, "what_if_limit", 1, "30s")), encoding="utf-8")),
    "30s without pnl_se": ("live", lambda lab: (lab / "live_fills" / "live_fills.json").write_text(
        json.dumps(without(LIVE_FILE, "what_if_limit", 1, "30s", "pnl_se")), encoding="utf-8")),
}


@pytest.mark.parametrize("why", list(BREAKS))
def test_a_missing_or_unreadable_prediction_is_null(home, monkeypatch, tmp_path, why):
    ledger(home).close()
    which, breaks = BREAKS[why]
    breaks(research_files(monkeypatch, tmp_path / "study"))
    p = dashboard.live_research("live-prod")["predictions"]
    assert p[which] is None
    assert p["live" if which == "history" else "history"] is not None    # the other file still counts


# ------------------------------------------------------------------ the experiment's orders
def test_the_orders_are_the_experiments_newest_first(home):
    experiment(home)
    r = dashboard.live_research("live-prod")
    assert [o["ticker"] for o in r["orders"]] == ["KXXRP15M-4", "KXDOGE15M-3", "KXETH15M-3", "KXSOL15M-2", "KXBTC15M-2",
                                                  "KXSOL15M-1", "KXETH15M-1", "KXBTC15M-1"]
    rows = {o["ticker"]: o for o in r["orders"]}
    same(rows["KXBTC15M-1"], {"ts": START, "ticker": "KXBTC15M-1", "side": "yes", "seen": 0.95, "limit": 0.96, "asked": 10,
                              "filled": 10, "base": 6, "extra": 4, "avgPaid": 0.954, "result": "won"})
    same(rows["KXETH15M-1"], {"ts": W1 + 481, "side": "no", "seen": 0.93, "limit": 0.94, "asked": 10, "filled": 5,
                              "base": 2, "extra": 3, "avgPaid": 4.68 / 5, "result": "lost"})
    same(rows["KXSOL15M-2"], {"ts": W2 + 481, "seen": 0.94, "limit": 0.95, "asked": 10, "filled": 0, "base": 0, "extra": 0,
                              "avgPaid": None, "result": None})          # nothing filled: no bet
    same(rows["KXDOGE15M-3"], {"filled": 6, "base": None, "extra": None, "avgPaid": 0.95, "result": "won"})   # unknown split
    same(rows["KXXRP15M-4"], {"filled": 3, "base": 1, "extra": 2, "avgPaid": 2.87 / 3, "result": "open"})


def test_at_most_50_orders_are_listed(home):
    db = ledger(home)
    trade(db, NOW - 10000, "KXBTC15M-OLD", 0.95, 0.95, 10)          # before: never listed
    for i in range(55):
        trade(db, NOW - 5000 + 60 * i, f"KXETH15M-{i:02d}", 0.95, 0.96, 10)
    db.commit()
    r = dashboard.live_research("live-prod")
    assert [o["ticker"] for o in r["orders"]] == [f"KXETH15M-{i:02d}" for i in range(54, 4, -1)]
    assert r["arms"]["during"]["orders"] == 55                        # the arm still counts every one
