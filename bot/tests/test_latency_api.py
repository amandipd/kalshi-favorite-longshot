"""The Latency tab's data (latency.py, and dashboard.py's /api/latency route).

Added Oct 15, 2026, and cut down the same day to the current setup only: with less than a week of data for each, a
comparison of setups said little. An order's latency here is its landing: how long after the minute-8 mark (480 s into its 15-minute window) Kalshi stamped
it. The stamp is Kalshi's own (ts_ms in its answer, on Kalshi's clock), so it doesn't depend on this PC's clock. Each
order also says how much of it filled.

latency.report(db) turns a ledger into the current setup's orders only, those Kalshi stamped since fast entry went live
(latency.SINCE, the Ohio server's go-live on Oct 16, 05:13:55 UTC), oldest first ([stamp, landing, share filled, contracts
asked]); their figures (latency.figures: median, each window's first order, the slow tail, the share filled); what the
setup does (SETUP), with no comparison to the setups before it; where the time goes now (WHERE, estimates); and what
could come next (NEXT). The history of older setups (ITERATIONS, QUIET, steps) is gone. It only reads.

    python -m pytest tests/test_latency_api.py -q
"""
import json
import os
import re
import sqlite3

import pytest

from kalshi_bot.web import dashboard
from kalshi_bot import fast_entry
from kalshi_bot.web import latency
from test_dashboard_more import fetch, home, serving  # noqa: F401  (home is a fixture)

SCHEMA = ("CREATE TABLE orders (id INTEGER PRIMARY KEY, ts REAL, ticker TEXT, client_order_id TEXT, request TEXT,"
          " http_status INTEGER, response TEXT)")
W = 1791936000          # a window's start: Oct 14, 2026, 00:00 UTC (a multiple of 900)
MARK = W + 480          # its minute-8 mark


def make_db(path=":memory:"):
    db = sqlite3.connect(str(path))
    db.execute(SCHEMA)
    return db


def add(db, landed, count=10, filled=5, status=201, ts=None, response=None, request=None):
    """One order Kalshi stamped `landed` s after a mark (landed: absolute stamp in seconds)."""
    req = request if request is not None else json.dumps({"ticker": "KXBTC15M-X", "count": str(count), "price": "0.9500"})
    if response is None:
        response = json.dumps({"fill_count": f"{filled:.2f}", "remaining_count": f"{count - filled:.2f}",
                               "ts_ms": round(landed * 1000)})
    db.execute("INSERT INTO orders (ts, ticker, request, http_status, response) VALUES (?, 'KXBTC15M-X', ?, ?, ?)",
               (landed - 2 if ts is None else ts, req, status, response))


# ------------------------------------------------------------------ each order
def test_an_orders_landing_is_kalshis_stamp_less_the_minute_8_mark():
    db = make_db()
    add(db, MARK + 0.323, count=10, filled=4)
    add(db, MARK + 900 + 3.957, count=8, filled=8)        # the next window
    assert latency.orders(db) == [[MARK + 0.323, 0.323, 0.4, 10], [MARK + 900 + 3.957, 3.957, 1.0, 8]]


def test_the_pcs_logged_time_doesnt_count_only_kalshis_stamp():
    db = make_db()
    add(db, MARK + 0.5, ts=MARK - 30)                      # the PC's clock 30 s off: the stamp still decides
    assert latency.orders(db)[0][1] == 0.5


def test_orders_come_oldest_first_by_kalshis_stamp():
    db = make_db()
    add(db, MARK + 900 + 1.0)
    add(db, MARK + 2.0)
    assert [o[1] for o in latency.orders(db)] == [2.0, 1.0]


def test_an_order_stamped_just_before_the_mark_lands_below_zero():
    db = make_db()
    add(db, MARK - 0.05)
    assert latency.orders(db)[0][1] == -0.05


def test_refused_or_unreadable_orders_are_left_out():
    db = make_db()
    add(db, MARK + 1, status=400, response=json.dumps({"error": {"code": "insufficient_balance"}}))   # no stamp
    add(db, MARK + 1, response="not json")
    add(db, MARK + 1, response=json.dumps(["a list"]))
    add(db, MARK + 1, response=json.dumps({"ts_ms": "soon"}))
    add(db, MARK + 1, response=None)
    db.execute("UPDATE orders SET response = NULL WHERE id = 5")
    add(db, MARK + 2)
    assert [o[1] for o in latency.orders(db)] == [2.0]


def test_the_share_filled_is_none_when_it_cant_be_read():
    db = make_db()
    add(db, MARK + 1, request="not json")
    add(db, MARK + 2, request=json.dumps({"count": "0"}))
    add(db, MARK + 3, response=json.dumps({"ts_ms": (MARK + 3) * 1000}))           # no fill_count
    assert [o[2:] for o in latency.orders(db)] == [[None, None], [None, None], [None, 10]]


def test_a_ledger_without_an_orders_table_has_no_orders():
    db = sqlite3.connect(":memory:")
    assert latency.orders(db) == []


def test_figures_are_rounded_to_the_millisecond_and_a_tenth_of_a_percent():
    db = make_db()
    add(db, MARK + 0.3234567, count=3, filled=1)
    stamp, landed, share, asked = latency.orders(db)[0]
    assert (landed, share, asked) == (0.323, 0.333, 3) and stamp == round(MARK + 0.323, 3)


# ------------------------------------------------------------------ the current setup only (Oct 15)
T0 = 1792127635          # the Ohio server went live: its bot started Oct 16, 2026, 05:13:55 UTC
M0 = T0 - T0 % 900 + 900 + 480   # the first minute-8 mark after it: Oct 16, 05:23 UTC


def test_the_tab_starts_when_the_ohio_server_went_live():
    assert latency.SINCE == T0                         # the server's first start, not the fast entry before it (Oct 14)
    assert latency.SINCE != fast_entry.START and latency.SINCE > 1792011884


def test_the_setup_and_estimates_describe_the_ohio_server_not_the_home_computer():
    """Oct 15: the bot moved to a server in Ohio, a few ms from Kalshi (probe: 3.9 ms median round trip)."""
    assert "Ohio" in latency.SETUP["what"]
    where = " ".join(r["step"] + " " + r["what"] for r in latency.WHERE)
    for before in ("Windows", "home", "relay", "15.6 ms"):   # the setup before it
        assert before not in where, before
    assert all(r["hi"] <= 15 for r in latency.WHERE), "every step is a few ms from Ohio"
    nxt = {r["title"]: r for r in latency.NEXT}
    assert nxt["A server in Ohio"]["status"] == "Done" and nxt["Kalshi's direct address"]["status"] == "Done"
    assert not any("cable" in t.lower() for t in nxt), "a server needs no network-cable idea"


def test_the_current_setup_is_explained_without_comparing_it_to_older_ones():
    s = latency.SETUP
    assert s["title"] == "Fast entry" and len(s["what"]) > 40
    assert not re.search(r"faster|sooner|slower|\d+ times|×|before|used to|instead of", s["what"], re.I), s["what"]


def test_the_history_and_its_comparisons_are_gone():
    for gone in ("ITERATIONS", "QUIET", "steps", "DAY"):
        assert not hasattr(latency, gone), gone


def test_the_figures_of_a_set_of_orders():
    db = make_db()
    for w, landed, filled in ((0, 0.40, 2), (0, 0.50, 4), (900, 0.30, 6), (1800, 0.20, 8), (1800, 0.90, 10)):
        add(db, M0 + w + landed, count=10, filled=filled)
    f = latency.figures(latency.orders(db))
    assert f == {"orders": 5, "windows": 3, "median": 0.4, "first": 0.3, "p95": pytest.approx(0.82, abs=0.001), "filled": 0.6}
    # first: the median of each window's first order (0.40, 0.30, 0.20); filled: 30 of 50 contracts


def test_no_orders_have_no_figures():
    assert latency.figures([]) == {"orders": 0, "windows": 0, "median": None, "first": None, "p95": None, "filled": None}


def test_the_slow_tail_is_the_95th_percentile():
    db = make_db()
    for i in range(20):
        add(db, M0 + i * 900 + (i + 1) / 10)
    assert latency.figures(latency.orders(db))["p95"] == pytest.approx(1.905, abs=0.01)


def test_unknown_fills_dont_drag_the_fill_share():
    db = make_db()
    add(db, M0 + 1, count=10, filled=5)
    add(db, M0 + 2, request="not json")
    assert latency.figures(latency.orders(db))["filled"] == 0.5


def test_the_fill_share_is_by_contract_not_by_order():
    db = make_db()
    add(db, M0 + 1, count=30, filled=30)
    add(db, M0 + 901, count=10, filled=0)
    assert latency.figures(latency.orders(db))["filled"] == 0.75   # 30 of 40, not the orders' 50%


def test_the_report_holds_only_the_current_setups_orders():
    db = make_db()
    add(db, T0 - 900 + 3.9)                            # the home computer, before the server: left out
    add(db, T0 - 0.5)                                  # a moment before the server's start: left out
    add(db, M0 + 0.3, count=10, filled=7)
    add(db, M0 + 900 + 0.4, count=10, filled=5)
    r = latency.report(db)
    assert set(r) == {"mark", "since", "setup", "orders", "figures", "where", "next"}
    assert r["mark"] == 480 and r["since"] == T0 and r["setup"] == latency.SETUP
    assert [o[1] for o in r["orders"]] == [0.3, 0.4] and r["orders"] == [o for o in latency.orders(db) if o[0] >= T0]
    assert r["figures"] == latency.figures(r["orders"]) and r["figures"]["orders"] == 2
    assert r["where"] == latency.WHERE and r["next"] == latency.NEXT
    json.dumps(r)                                      # it travels as JSON


def test_where_the_time_goes_and_whats_next_are_listed():
    for row in latency.WHERE:
        assert set(row) >= {"step", "lo", "hi", "what"} and 0 <= row["lo"] <= row["hi"]
    assert len(latency.WHERE) >= 4
    for row in latency.NEXT:
        assert set(row) >= {"title", "what", "saves", "status"}
    assert len(latency.NEXT) >= 4


# ------------------------------------------------------------------ the route
def ledger(home, name="live-prod"):
    db = make_db(home.dir / f"{name}.db")
    add(db, MARK + 3.9)                                # the old loop, before fast entry: not on the tab
    add(db, M0 + 0.3)
    db.commit()
    db.close()


def test_the_route_answers_for_the_real_money_mode_first(home):
    for name in ("live-demo", "live-prod"):
        ledger(home, name)
    with serving() as base:
        status, headers, body = fetch(base, "/api/latency")
    assert status == 200 and headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
    r = json.loads(body)
    assert r["mode"] == "live-prod" and [o[1] for o in r["orders"]] == [0.3] and "now" in r
    assert r["since"] == T0 and r["figures"]["orders"] == 1 and r["setup"]["title"] == "Fast entry" and "steps" not in r


def test_the_route_reads_another_mode_only_if_it_exists(home):
    ledger(home, "live-prod")
    ledger(home, "live-demo")
    with serving() as base:
        assert json.loads(fetch(base, "/api/latency?mode=live-demo")[2])["mode"] == "live-demo"
        assert json.loads(fetch(base, "/api/latency?mode=../../etc")[2])["mode"] == "live-prod"


def test_the_route_says_so_before_any_ledger_exists(home):
    with serving() as base:
        assert json.loads(fetch(base, "/api/latency")[2]) == {"error": "no live records yet"}


def test_the_route_never_changes_the_ledger(home):
    ledger(home)
    before = sorted(os.listdir(home.dir))
    path = home.dir / "live-prod.db"
    stat = path.stat().st_mtime_ns
    with serving() as base:
        for _ in range(3):
            fetch(base, "/api/latency")
    assert sorted(os.listdir(home.dir)) == before and path.stat().st_mtime_ns == stat


def test_the_tabs_files_are_served():
    assert dashboard.ASSETS["/latency.js"] == ("latency.js", "text/javascript; charset=utf-8")
    assert dashboard.ASSETS["/latency.css"] == ("latency.css", "text/css; charset=utf-8")


def test_the_tabs_files_come_back_from_the_server(home):
    with serving() as base:
        for path, kind in (("/latency.js", "text/javascript"), ("/latency.css", "text/css")):
            status, headers, body = fetch(base, path)
            assert status == 200 and headers["Content-Type"].startswith(kind) and body
