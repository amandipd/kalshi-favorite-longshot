"""Contracts filled in the last hour, beside the last 24 hours and all time.

Orders filled in the last hour, on the Live tab too. The Live tab's Orders header
says how the buy orders filled over the last 24 hours (state()["fills"]) and over all time (state()["fillsAll"]). state()
now also sends "fillsHour": the same figures over the buy orders sent in the last hour (3600 s, counted the same way: a
missing count is 0 asked; an order Kalshi refused, or whose answer never came back, filled 0 and got none). Every order
in that hour counts, not only the 30 the table lists (a busy hour has sent 34). "fills" and "fillsAll" don't change.

ordersBlock() puts the hour's line first in the Orders fold's header meta, a line of its own above the 24-hour one:
"last hour: 30 of 45 contracts filled (67%) · 1 of 3 orders got none", or "none in the last hour" when the hour sent no
order. No hour line when the server sends no fillsHour (a dashboard not yet restarted: the header reads exactly as
today), nor when the last 24 hours sent none (the day's "none in the last 24 hours" says it). The page is cut out with
the helpers it uses and run in node, as test_fills_all.py does (skipped without node); one check loads the whole Live
tab with test_folds_live.py's stand-in browser.

    python -m pytest -q -p no:cacheprovider tests/test_fills_hour.py
"""

import json
import os
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, home, mode_db, order  # noqa: F401  (home is a fixture)
from test_fills_all import ALL, ALL_LINE, DAY_LINE, FILLS, NO_FILLS, an_order, cancel, header_and_body, text
from test_folds_live import fold_helper, golden, missing, run
from test_order_results import NODE, SCRIPT, needs_node, piece

HOUR = 3600
EMPTY = {"orders": 0, "asked": 0, "filled": 0, "none": 0}


# ------------------------------------------------------------------ the server: the last hour's buy orders
def test_the_last_hours_buy_orders_are_counted_as_the_day_is(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 2 * HOUR, "KXBTC15M-EARLIER", response='{"fill_count": "15.00"}')             # today, not this hour
    order(db, NOW - 3000, "KXETH15M-A", response='{"fill_count": "0.00"}')                        # 15 asked, none filled
    order(db, NOW - 2000, "KXXRP15M-A", side="ask", price="0.0750")                               # 4 of 15
    order(db, NOW - 1000, "KXSOL15M-A", count="16", response='{"fill_count": "2.50"}')            # 2.5 of 16
    order(db, NOW - 500, "KXDOGE15M-A", status=400, response='{"error": {"message": "insufficient balance"}}')   # refused
    order(db, NOW - 400, "KXHYPE15M-A", status=None, response='"network error: timed out"')                     # no answer
    order(db, NOW - 300, "KXBNB15M-A", count=None, response='{"fill_count": "0.00"}')                           # no count
    cancel(db, NOW - 50)                                                                          # a cancel, not an order
    db.commit()
    s = dashboard.state("live-prod")
    assert s["fillsHour"] == {"orders": 6, "asked": 76.0, "filled": 6.5, "none": 4}
    assert s["fills"] == {"orders": 7, "asked": 91.0, "filled": 21.5, "none": 4}                  # the day: as before


def test_an_order_exactly_an_hour_old_counts_and_one_a_second_older_doesnt(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - HOUR, "KXBTC15M-EDGE")                                                        # 4 of 15
    order(db, NOW - HOUR - 1, "KXETH15M-OLDER", response='{"fill_count": "15.00"}')
    db.commit()
    assert dashboard.state("live-prod")["fillsHour"] == {"orders": 1, "asked": 15.0, "filled": 4.0, "none": 0}


def test_every_order_of_the_hour_counts_not_just_the_ones_listed(home):
    db = mode_db(home, "live-prod")
    for i in range(34):                                                                           # a busy hour: over 30
        order(db, NOW - HOUR + 60 + i * 100, f"KXBTC15M-{i:02d}")                                 # 4 of 15 each
    db.commit()
    s = dashboard.state("live-prod")
    assert len(s["orders"]) == dashboard.ORDERS_SHOWN < 34
    assert s["fillsHour"] == {"orders": 34, "asked": 510.0, "filled": 136.0, "none": 0}


def test_the_hour_follows_the_clock(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 600, "KXBTC15M-A")
    db.commit()
    assert dashboard.state("live-prod")["fillsHour"]["orders"] == 1
    home.clock[0] += HOUR                                                                         # an hour on: it's 70 min old
    s = dashboard.state("live-prod")
    assert s["fillsHour"] == EMPTY and s["fills"]["orders"] == 1


@pytest.mark.parametrize("cancels", [0, 2])
def test_with_no_buy_orders_the_hour_is_empty(home, cancels):
    db = mode_db(home, "live-prod")
    for i in range(cancels):
        cancel(db, NOW - 100 * (i + 1))
    db.commit()
    assert dashboard.state("live-prod")["fillsHour"] == EMPTY


def test_the_hour_has_the_days_shape_and_the_other_figures_are_unchanged(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-A")
    order(db, NOW - 3 * 86400, "KXETH15M-OLD", response='{"fill_count": "15.00"}')
    db.commit()
    s = dashboard.state("live-prod")
    assert set(s["fillsHour"]) == set(s["fills"]) == {"orders", "asked", "filled", "none"}
    assert s["fillsHour"] == s["fills"] == {"orders": 1, "asked": 15.0, "filled": 4.0, "none": 0}
    assert s["fillsAll"] == {"orders": 2, "asked": 30.0, "filled": 19.0, "none": 0, "since": NOW - 3 * 86400}
    json.dumps(s["fillsHour"])                                                                    # the API sends it as JSON


# ------------------------------------------------------------------ the page: the Orders header, run in node
HOUR_FILLS = {"orders": 3, "asked": 45, "filled": 30, "none": 1}
HOUR_LINE = "last hour: 30 of 45 contracts filled (67%) · 1 of 3 orders got none"


def orders_html(fills, fills_all=..., fills_hour=..., orders=None):
    """What ordersBlock() writes for a state with these figures; one left out = an old server's state without it."""
    state = {"orders": [an_order()] if orders is None else orders, "fills": fills}
    if fills_all is not ...:
        state["fillsAll"] = fills_all
    if fills_hour is not ...:
        state["fillsHour"] = fills_hour
    js = "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "nf", "zero", "signed", "pct", "count", "cents", "hhmm",
                                                          "sym", "title", "ICON_LIST", "emptyState")),
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
    return r.stdout.replace(" ", " ").replace("\xa0", " ")


def lines(meta):
    """The meta's lines: each <span class="fm-ln">'s words, or the whole meta as one line when it has none."""
    parts = meta.split('<span class="fm-ln">')[1:]
    return [text(p) for p in parts] if parts else [text(meta)]


@needs_node
def test_the_hours_line_comes_first_above_the_days_and_all_times():
    meta, body = header_and_body(orders_html(FILLS, ALL, HOUR_FILLS))
    assert lines(meta) == [HOUR_LINE, DAY_LINE, ALL_LINE]
    assert meta.count('<span class="fm-ln">') == 3                                 # a line each
    assert "last hour" not in body                                                 # in the header, not the table


@needs_node
def test_the_hours_line_shows_while_the_orders_are_folded():
    html = orders_html(FILLS, ALL, HOUR_FILLS)
    _, body = header_and_body(html)
    assert body.split(">", 1)[0].endswith(" hidden")                               # Orders starts folded ...
    assert html.count("last hour:") == 1                                           # ... and the line is still in view


@needs_node
def test_an_hour_with_no_orders_says_so():
    meta, _ = header_and_body(orders_html(FILLS, ALL, EMPTY))
    assert lines(meta) == ["none in the last hour", DAY_LINE, ALL_LINE]


@needs_node
def test_with_no_all_time_figures_the_hour_and_the_day_are_a_line_each():
    meta, _ = header_and_body(orders_html(FILLS, fills_hour=HOUR_FILLS))
    assert lines(meta) == [HOUR_LINE, DAY_LINE] and meta.count('<span class="fm-ln">') == 2


@needs_node
@pytest.mark.parametrize("fills_all", [..., ALL], ids=["no-all-time", "all-time"])
def test_an_old_server_with_no_hours_figures_draws_todays_header(fills_all):
    meta, _ = header_and_body(orders_html(FILLS, fills_all))
    assert lines(meta) == ([DAY_LINE] if fills_all is ... else [DAY_LINE, ALL_LINE])
    assert "last hour" not in meta


@needs_node
@pytest.mark.parametrize("hour", [EMPTY, HOUR_FILLS], ids=["empty-hour", "hour"])
def test_a_day_with_no_orders_draws_no_hour_line(hour):
    meta, _ = header_and_body(orders_html(NO_FILLS, ALL, hour))
    assert lines(meta) == ["none in the last 24 hours", ALL_LINE]                  # the day's "none" says it
    assert "last hour" not in meta


@needs_node
def test_figures_read_as_the_days_do():
    meta, _ = header_and_body(orders_html(FILLS, ALL, {"orders": 7, "asked": 98, "filled": 52.25, "none": 2}))
    assert lines(meta)[0] == "last hour: 52.25 of 98 contracts filled (53%) · 2 of 7 orders got none"   # 53.3%: 0 places
    meta, _ = header_and_body(orders_html(FILLS, ALL, {"orders": 2, "asked": 30, "filled": 30, "none": 0}))
    assert lines(meta)[0] == "last hour: 30 of 30 contracts filled (100%) · 0 of 2 orders got none"


@needs_node
def test_the_title_count_and_the_body_are_unchanged():
    with_hour, without = orders_html(FILLS, ALL, HOUR_FILLS), orders_html(FILLS, ALL)
    assert with_hour.split('<div class="fold-h">')[0] == without.split('<div class="fold-h">')[0]
    assert with_hour.split('<div class="fold-body"', 1)[1] == without.split('<div class="fold-body"', 1)[1]
    title = with_hour.split('<span class="fold-m">')[0]
    assert title == without.split('<span class="fold-m">')[0]                     # the title and its count


# ------------------------------------------------------------------ the whole Live tab
@needs_node
def test_the_live_tab_shows_the_hours_line_and_loses_no_word():
    g = golden()
    page = run(inputs={**g, "state": {**g["state"], "fillsHour": HOUR_FILLS}})[0]
    f = page.fold("live.orders")
    assert HOUR_LINE in f.meta and not f.shown                                     # in the folded Orders header
    assert not missing(page), f"words of today's Live tab are gone: {missing(page)}"
