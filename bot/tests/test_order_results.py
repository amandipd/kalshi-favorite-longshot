"""The Live tab's Orders table says how each order's contracts did: won, lost, or still open.

state() joins each listed buy order to its bet by ticker (one buy order per market; bets.ticker is unique) and adds the
bet's result, its P&L once settled, and when it settles. ordersBlock() shows that in a last "Result" column: "Won"
with the gain, "Lost" with the loss, "Open" with the time it settles, or a dash when no bet came of the order. To make
room on a phone, the "Asked" column hides there ("Filled" already says what share filled). The page is cut out with
the helpers it uses (with the shared fold helper it draws through once the Live tab folds) and run in
node on a state like /api/state's (skipped without node).
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, add_bet, home, mode_db, order  # noqa: F401  (home is a fixture)
from test_folds_live import fold_helper

HTML = open(dashboard.PAGE, encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)   # the page's own script, as test_frontend.py cuts it
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")


# ------------------------------------------------------------------ the server: each order gets its bet's result
def by_ticker(s):
    return {o["ticker"]: o for o in s["orders"]}


def test_each_order_says_whether_its_contracts_won_lost_or_are_still_open(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 400, "KXBTC15M-W", response='{"fill_count": "3.00"}')
    order(db, NOW - 300, "KXETH15M-L", response='{"fill_count": "3.00"}')
    order(db, NOW - 200, "KXSOL15M-O", response='{"fill_count": "3.00"}')
    order(db, NOW - 100, "KXXRP15M-N", response='{"fill_count": "0.00"}')          # nothing filled: no bet
    db.commit()
    add_bet(db, "KXBTC15M-W", status="won", pnl=0.62, placed=NOW - 400)
    add_bet(db, "KXETH15M-L", status="lost", pnl=-15.49, placed=NOW - 300)
    add_bet(db, "KXSOL15M-O", status="open", placed=NOW - 200)
    o = by_ticker(dashboard.state("live-prod"))
    assert (o["KXBTC15M-W"]["result"], o["KXBTC15M-W"]["pnl"], o["KXBTC15M-W"]["close_ts"]) == ("won", 0.62, NOW - 400 + 420)
    assert (o["KXETH15M-L"]["result"], o["KXETH15M-L"]["pnl"], o["KXETH15M-L"]["close_ts"]) == ("lost", -15.49, NOW - 300 + 420)
    assert (o["KXSOL15M-O"]["result"], o["KXSOL15M-O"]["pnl"], o["KXSOL15M-O"]["close_ts"]) == ("open", None, NOW - 200 + 420)
    assert (o["KXXRP15M-N"]["result"], o["KXXRP15M-N"]["pnl"], o["KXXRP15M-N"]["close_ts"]) == (None, None, None)


def test_an_order_refused_by_kalshi_has_no_result(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXDOGE15M-R", status=400, response='{"error": {"message": "insufficient balance"}}')
    db.commit()
    o = dashboard.state("live-prod")["orders"][0]
    assert (o["filled"], o["error"], o["result"], o["pnl"], o["close_ts"]) == (None, "insufficient balance", None, None, None)


def test_an_order_whose_answer_never_came_back_still_shows_the_bet_its_fills_made(home):
    # No answer from Kalshi, but the bot found the order's fills and recorded a bet: that bet is how the order did.
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-T", status=None, response='"network error: timed out"')
    db.commit()
    add_bet(db, "KXBTC15M-T", status="lost", pnl=-9.75, placed=NOW - 100)
    o = dashboard.state("live-prod")["orders"][0]
    assert (o["filled"], o["error"]) == (None, "no answer from Kalshi")
    assert (o["result"], o["pnl"]) == ("lost", -9.75)


def test_an_open_order_turns_won_once_its_bet_settles(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-S", response='{"fill_count": "3.00"}')
    db.commit()
    add_bet(db, "KXBTC15M-S", status="open", placed=NOW - 100)
    assert by_ticker(dashboard.state("live-prod"))["KXBTC15M-S"]["result"] == "open"
    db.execute("UPDATE bets SET status='won', pnl=0.14, settled_ts=? WHERE ticker='KXBTC15M-S'", (NOW + 400,))
    db.commit()
    o = by_ticker(dashboard.state("live-prod"))["KXBTC15M-S"]
    assert (o["result"], o["pnl"]) == ("won", 0.14)


def test_a_bet_without_a_listed_order_changes_nothing(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-A", response='{"fill_count": "3.00"}')
    db.commit()
    add_bet(db, "KXETH15M-OTHER", status="won", placed=NOW - 5000)               # its order isn't in the table
    s = dashboard.state("live-prod")
    assert [o["ticker"] for o in s["orders"]] == ["KXBTC15M-A"] and s["orders"][0]["result"] is None


def test_the_days_fill_summary_and_order_row_are_unchanged(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXETH15M-A", response='{"fill_count": "0.00"}')
    order(db, NOW - 200, "KXXRP15M-A")                                           # 4 of 15
    db.commit()
    add_bet(db, "KXXRP15M-A", status="won", contracts=4, placed=NOW - 200)
    assert dashboard.state("live-prod")["fills"] == {"orders": 2, "asked": 30.0, "filled": 4.0, "none": 1}
    row = {"ts": NOW, "ticker": "KXXRP15M-A", "request": json.dumps({"side": "bid", "count": "15", "price": "0.9300"}),
           "http_status": 201, "response": '{"fill_count": "4.00"}'}
    assert "result" not in dashboard.order_row(row)                              # the join happens in state(), not per row


# ------------------------------------------------------------------ the page: the Result column, run in node
def piece(pattern):
    m = re.search(pattern, SCRIPT, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def orders_html(orders):
    js = "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "nf", "zero", "signed", "pct", "cents", "hhmm", "sym",
                                                          "title", "ICON_LIST", "emptyState")),
        piece(r"^const when = \(t\) => \{.*?^\};$"),
        piece(r"^const kalshiUrl = \(ticker\) => \{.*?^\};$"),
        piece(r"^const market = [^\n]*$"),
        piece(r"^function table\(id, head, rows, empty\) \{.*?^\}$"),
        piece(r"^function ordersBlock\(\) \{.*?^\}$"),
        fold_helper(SCRIPT),   # the orders draw inside a fold once the Live tab folds (empty before that)
        "const fullTables = new Set(), out = {};",
        "function patch(id, html) { out[id] = html; return true; }",
        "const data = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "ordersBlock();",
        "process.stdout.write(Object.values(out).join(''));",   # every region it wrote
    ])
    state = {"orders": orders, "fills": {"orders": len(orders), "asked": 15.0 * len(orders), "filled": 3.0, "none": 0}}
    r = subprocess.run([NODE, "-e", js], input=json.dumps(state), capture_output=True, text=True, encoding="utf-8",
                       timeout=30, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return r.stdout.replace(" ", " ").replace("\xa0", " ")                  # node writes "3:45 PM" with a narrow space


def an_order(**more):
    return {"ts": NOW - 400, "ticker": "KXBTC15M-26SEP281500-00", "series": "KXBTC15M", "side": "yes", "price": 0.95,
            "asked": 15.0, "filled": 15.0, "error": None, "result": None, "pnl": None, "close_ts": None, **more}


def result_cell(html):
    cells = re.findall(r"<td[^>]*>.*?</td>", html.split("<tbody>")[1].split("</tr>")[0], re.S)
    return cells[-1]


@needs_node
def test_the_table_has_a_result_column_last():
    html = orders_html([an_order()])
    heads = re.findall(r"<th scope=\"col\" class=\"([^\"]*)\">([^<]*)</th>", html)
    assert heads == [("", "Placed"), ("", "Market"), ("", "Side · price"), ("num hide-sm", "Asked"), ("num", "Filled"),
                     ("num", "Result")]


@needs_node
def test_a_won_order_says_won_with_its_gain():
    cell = result_cell(orders_html([an_order(result="won", pnl=0.62, close_ts=NOW + 20)]))
    assert cell == '<td class="num up">Won<span class="s muted" style="display:block">+$0.62</span></td>'


@needs_node
def test_a_lost_order_says_lost_with_its_loss():
    cell = result_cell(orders_html([an_order(result="lost", pnl=-15.49, close_ts=NOW + 20)]))
    assert cell == '<td class="num down">Lost<span class="s muted" style="display:block">−$15.49</span></td>'


@needs_node
def test_an_open_order_says_when_it_settles():
    cell = result_cell(orders_html([an_order(result="open", close_ts=NOW + 2700)]))   # 3:45 PM ET
    assert cell == '<td class="num muted">Open<span class="s muted" style="display:block">settles 3:45 PM</span></td>'


@needs_node
def test_an_order_with_no_bet_shows_a_dash():
    for o in (an_order(filled=0.0), an_order(filled=None, error="insufficient balance")):
        assert result_cell(orders_html([o])) == '<td class="num muted">—</td>'


@needs_node
@pytest.mark.parametrize("odd", ["void", "<img src=x onerror=alert(1)>", "WON", 1])
def test_a_result_it_doesnt_know_shows_a_dash_and_is_never_printed(odd):
    html = orders_html([an_order(result=odd, pnl=1.0, close_ts=NOW)])
    assert result_cell(html) == '<td class="num muted">—</td>'
    assert "<img" not in html and "void" not in html


@needs_node
def test_the_asked_column_hides_on_a_phone_and_the_rest_of_the_row_is_as_before():
    html = orders_html([an_order(asked=16.0, filled=6.0, result="open", close_ts=NOW + 2700)])
    cells = re.findall(r"<td[^>]*>.*?</td>", html.split("<tbody>")[1].split("</tr>")[0], re.S)
    assert len(cells) == 6
    assert cells[3] == '<td class="num hide-sm">16</td>'
    assert cells[4] == ('<td class="num part">6<span class="only-sm"> of 16</span>'   # asked, on a phone (test_orders_at_ask.py)
                        '<span class="s muted" style="display:block">38% filled</span></td>')
    assert '<span class="pill yes">YES 95¢</span>' in cells[2]
    assert "2:45 PM–3:00 PM window" in cells[0]


@needs_node
def test_each_row_gets_its_own_result():
    html = orders_html([an_order(ticker="KXBTC15M-A", result="won", pnl=0.5, close_ts=NOW),
                        an_order(ticker="KXETH15M-B", result="lost", pnl=-9.0, close_ts=NOW),
                        an_order(ticker="KXSOL15M-C")])
    rows = html.split("<tbody>")[1].split("</tr>")[:3]
    last = [re.findall(r"<td[^>]*>.*?</td>", r, re.S)[-1] for r in rows]
    assert ["Won" in last[0], "Lost" in last[1], last[2] == '<td class="num muted">—</td>'] == [True, True, True]


def test_the_section_is_labelled_for_screen_readers():
    assert '<section id="orders" aria-label="Orders: asked for, filled, won or lost"></section>' in HTML
