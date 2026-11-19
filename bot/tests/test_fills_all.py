"""Contracts filled over all time, beside the last 24 hours.

Contracts filled over the last 24 hours and over all time. The Live tab's Orders header says how the
last day's buy orders filled ("last 24 hours: 5229.48 of 8608 contracts filled (61%) · 74 of 303 orders got none"),
from state()["fills"]. state() now also sends "fillsAll": the same figures over every buy order in the ledger, however
old, counted the same way (a missing count is 0 asked; an order Kalshi refused, or whose answer never came back, filled
0 and got none), plus "since", when the first buy order went out. Cancels aren't buy orders and don't count. "fills"
itself doesn't change.

ordersBlock() keeps the 24-hour line as it is and adds the all-time one after it, in the Orders fold's header meta (so
it shows while Orders is folded, as it is at first): "all time (since Sep 28): 8013.69 of 13760 contracts filled (58%)
· 193 of 720 orders got none". No "(since …)" when since is null; no all-time line when the server sends no fillsAll
(a dashboard not yet restarted: the header reads exactly as today) or when nothing was ever asked for. The page is cut
out with the helpers it uses and run in node with the clock's time zone fixed and an en-US locale (skipped without
node).

    python -m pytest tests/test_fills_all.py -q
"""

import json
import os
import re
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, home, mode_db, order  # noqa: F401  (home is a fixture)
from test_folds_live import fold_helper
from test_order_results import NODE, SCRIPT, needs_node, piece

DAY = 86400
EMPTY = {"orders": 0, "asked": 0, "filled": 0, "none": 0, "since": None}


def cancel(db, ts, ticker="KXXRP15M-A"):
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, "c", '{"cancel": "abc"}', 200, '{}'))


# ------------------------------------------------------------------ the server: every buy order, however old
def test_every_buy_order_counts_however_old_and_the_days_figures_are_unchanged(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 20 * DAY, "KXBTC15M-OLD", response='{"fill_count": "15.00"}')                 # weeks ago: all 15
    order(db, NOW - 90_000, "KXSOL15M-OLD", count="16", response='{"fill_count": "2.50"}')       # over a day ago
    order(db, NOW - 300, "KXETH15M-A", response='{"fill_count": "0.00"}')                         # nothing filled
    order(db, NOW - 200, "KXXRP15M-A", side="ask", price="0.0750")                                # 4 of 15
    order(db, NOW - 100, "KXDOGE15M-A", status=400, response='{"error": {"message": "insufficient balance"}}')
    cancel(db, NOW - 50)                                                                          # a cancel, not an order
    db.commit()
    s = dashboard.state("live-prod")
    assert s["fillsAll"] == {"orders": 5, "asked": 76.0, "filled": 21.5, "none": 2, "since": NOW - 20 * DAY}
    assert s["fills"] == {"orders": 3, "asked": 45.0, "filled": 4.0, "none": 2}                  # the last 24 hours, as before


def test_counted_as_the_day_is_counted(home):
    # a missing count asks for 0; refused, unanswered and nothing-filled orders fill 0 and got none
    db = mode_db(home, "live-prod")
    order(db, NOW - 5 * DAY, "KXBTC15M-NOCOUNT", count=None, response='{"fill_count": "0.00"}')
    order(db, NOW - 4 * DAY, "KXETH15M-REFUSED", status=400, response='{"error": {"message": "insufficient balance"}}')
    order(db, NOW - 3 * DAY, "KXSOL15M-NOANSWER", status=None, response='"network error: timed out"')
    order(db, NOW - 2 * DAY, "KXXRP15M-NOFILLCOUNT", response='{"order_id": "x"}')
    order(db, NOW - 2 * DAY + 900, "KXHYPE15M-SERVERERR", status=500, response='{"detail": "oops"}')
    order(db, NOW - 1 * DAY - 60, "KXDOGE15M-PART", count="16", response='{"fill_count": "3.40"}')
    db.commit()
    assert dashboard.state("live-prod")["fillsAll"] == {"orders": 6, "asked": 76.0, "filled": 3.4, "none": 5,
                                                        "since": NOW - 5 * DAY}


def test_over_the_last_day_alone_all_time_is_the_days_figures(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 3000, "KXBTC15M-A", response='{"fill_count": "15.00"}')
    order(db, NOW - 2000, "KXETH15M-A", count="16", response='{"fill_count": "6.00"}')
    order(db, NOW - 1000, "KXSOL15M-A", status=None, response='"network error: timed out"')
    db.commit()
    s = dashboard.state("live-prod")
    assert {k: v for k, v in s["fillsAll"].items() if k != "since"} == s["fills"]
    assert s["fillsAll"]["since"] == NOW - 3000


def test_since_is_the_first_buy_order_sent_not_the_first_written_nor_a_cancel(home):
    db = mode_db(home, "live-prod")
    cancel(db, NOW - 30 * DAY)                                                                    # older, but a cancel
    order(db, NOW - 500, "KXETH15M-NEW")
    order(db, NOW - 9 * DAY, "KXBTC15M-FIRST")                                                    # written later, sent first
    order(db, NOW - 2 * DAY, "KXSOL15M-MID")
    db.commit()
    assert dashboard.state("live-prod")["fillsAll"]["since"] == NOW - 9 * DAY


def test_every_order_counts_not_just_the_ones_listed(home):
    db = mode_db(home, "live-prod")
    for i in range(40):                                                                           # more than ORDERS_SHOWN
        order(db, NOW - 3 * DAY + i * 3600, f"KXBTC15M-{i:02d}")                                  # 4 of 15 each
    db.commit()
    s = dashboard.state("live-prod")
    assert len(s["orders"]) == dashboard.ORDERS_SHOWN < 40
    assert s["fillsAll"] == {"orders": 40, "asked": 600.0, "filled": 160.0, "none": 0, "since": NOW - 3 * DAY}


@pytest.mark.parametrize("cancels", [0, 2])
def test_with_no_buy_orders_all_time_is_empty(home, cancels):
    db = mode_db(home, "live-prod")
    for i in range(cancels):
        cancel(db, NOW - 1000 * (i + 1))
    db.commit()
    s = dashboard.state("live-prod")
    assert s["fillsAll"] == EMPTY
    assert s["fills"] == {"orders": 0, "asked": 0, "filled": 0, "none": 0}


def test_both_have_the_same_shape_and_all_time_adds_since(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-A")
    db.commit()
    s = dashboard.state("live-prod")
    assert set(s["fills"]) == {"orders", "asked", "filled", "none"}
    assert set(s["fillsAll"]) == {"orders", "asked", "filled", "none", "since"}
    json.dumps(s["fillsAll"])                                                                     # the API sends it as JSON


# ------------------------------------------------------------------ the page: the Orders header, run in node
DAY_LINE = "last 24 hours: 5229.48 of 8608 contracts filled (61%) · 74 of 303 orders got none"   # the spec's figures
FILLS = {"orders": 303, "asked": 8608, "filled": 5229.48, "none": 74}
NO_FILLS = {"orders": 0, "asked": 0, "filled": 0, "none": 0}
SINCE = NOW - 10 * DAY                                                                            # Sep 18, 3 PM ET
ALL = {"orders": 720, "asked": 13760, "filled": 8013.69, "none": 193, "since": SINCE}
ALL_LINE = "all time (since Sep 18): 8013.69 of 13760 contracts filled (58%) · 193 of 720 orders got none"


def an_order(**more):
    return {"ts": NOW - 400, "ticker": "KXBTC15M-26SEP281500-00", "series": "KXBTC15M", "side": "yes", "price": 0.95,
            "asked": 15.0, "filled": 15.0, "error": None, "result": None, "pnl": None, "close_ts": None, **more}


def orders_html(fills, fills_all=..., orders=None):
    """What ordersBlock() writes for a state with these figures; fills_all left out = an old server's state."""
    state = {"orders": [an_order()] if orders is None else orders, "fills": fills}
    if fills_all is not ...:
        state["fillsAll"] = fills_all
    js = "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "nf", "zero", "signed", "pct", "cents", "hhmm", "sym",
                                                          "title", "ICON_LIST", "emptyState")),
        piece(r"^const when = \(t\) => \{.*?^\};$"),
        piece(r"^const kalshiUrl = \(ticker\) => \{.*?^\};$"),
        piece(r"^const market = [^\n]*$"),
        piece(r"^function table\(id, head, rows, empty\) \{.*?^\}$"),
        piece(r"^function ordersBlock\(\) \{.*?^\}$"),
        fold_helper(SCRIPT),
        "const fullTables = new Set(), out = {};",
        "function patch(id, html) { out[id] = html; return true; }",
        "const data = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "ordersBlock();",
        "process.stdout.write(Object.values(out).join(''));",
    ])
    r = subprocess.run([NODE, "-e", js], input=json.dumps(state), capture_output=True, text=True, encoding="utf-8",
                       timeout=30, env={**os.environ, "TZ": "America/New_York", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"})
    assert r.returncode == 0, r.stderr
    return r.stdout.replace(" ", " ").replace("\xa0", " ")


def header_and_body(html):
    """The fold's header meta (outside the button, still shown when folded) and its body, as the shared fold lays them out."""
    head, body = html.split('<div class="fold-body"', 1)
    assert head.count('<span class="fold-m">') == 1, head
    meta = head.split('<span class="fold-m">', 1)[1]
    assert meta.endswith("</span></div>"), meta
    return meta[:-len("</span></div>")], body


def text(meta):
    """The meta's words as read: markup (a line break, a span per line) between them is only a gap."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", meta)).strip()


@needs_node
def test_the_all_time_line_follows_the_days_line_in_the_orders_header():
    html = orders_html(FILLS, ALL)
    meta, body = header_and_body(html)
    assert text(meta) == f"{DAY_LINE} {ALL_LINE}"
    assert "all time" not in body and html.count("all time") == 1                # in the header, not the table
    assert re.match(r'[^>]* hidden>', body)                                        # Orders starts folded: the line shows anyway


@needs_node
def test_a_whole_number_filled_shows_no_decimals():
    meta, _ = header_and_body(orders_html(FILLS, {**ALL, "filled": 9000}))
    assert text(meta).endswith("all time (since Sep 18): 9000 of 13760 contracts filled (65%) · 193 of 720 orders got none")


@needs_node
def test_the_date_is_the_first_orders_day_where_the_page_is():
    late = NOW - 10 * DAY + 7 * 3600                                               # Sep 18, 10 PM ET: Sep 19 in UTC
    meta, _ = header_and_body(orders_html(FILLS, {**ALL, "since": late}))
    assert "all time (since Sep 18): " in text(meta)


@needs_node
def test_no_since_no_date():
    meta, _ = header_and_body(orders_html(FILLS, {**ALL, "since": None}))
    assert text(meta) == f"{DAY_LINE} all time: 8013.69 of 13760 contracts filled (58%) · 193 of 720 orders got none"
    assert "since" not in meta and "null" not in meta


@needs_node
def test_none_in_the_last_day_but_some_all_time():
    meta, _ = header_and_body(orders_html(NO_FILLS, ALL))
    assert text(meta) == f"none in the last 24 hours {ALL_LINE}"


@needs_node
@pytest.mark.parametrize("fills_all", [..., None], ids=["no fillsAll", "fillsAll null"])
@pytest.mark.parametrize("fills, line", [(FILLS, DAY_LINE), (NO_FILLS, "none in the last 24 hours")], ids=["day", "no day"])
def test_an_old_server_without_all_time_reads_as_today(fills, line, fills_all):
    html = orders_html(fills, fills_all)
    meta, _ = header_and_body(html)
    assert meta == line                                                            # exactly today's header, markup and all
    for bad in ("all time", "undefined", "NaN", "null"):
        assert bad not in html


@needs_node
@pytest.mark.parametrize("fills_all", [EMPTY, {"orders": 3, "asked": 0, "filled": 0, "none": 3, "since": SINCE}],
                         ids=["no orders ever", "none asked for anything"])
@pytest.mark.parametrize("fills, line", [(FILLS, DAY_LINE), (NO_FILLS, "none in the last 24 hours")], ids=["day", "no day"])
def test_nothing_ever_asked_for_no_all_time_line(fills, line, fills_all):
    html = orders_html(fills, fills_all)
    meta, _ = header_and_body(html)
    assert meta == line
    assert "all time" not in html and "NaN" not in html
