"""What was on offer at the ask for each order, beside what it asked for and what it got.

How many contracts were on offer at the ask for each order, and how many each order asked for, on the Live tab.
Since Oct 12 the bot reads the order book at minute 8 for every order and
keeps it in the ledger's shadow table: the 'fast' row's `extra` is the contracts the book offered at the order's price
then (the bot's own read since the Oct 14 fast-entry restart, the mark reader's before), and the 'limitup' row's
`extra` is the contracts on offer within 1¢ over it just after (on top of what filled). With those beside "asked" and
"filled", a miss reads at a glance: nothing on offer, on offer but taken first, or the price moved up.

The server: state()'s listed orders each gain "atAsk" (the order's ticker's 'fast' row's extra) and "plusOne" (its
'limitup' row's extra), None when there's no such row or the ledger has no shadow table yet.

The page: ordersBlock() adds an "At the ask" column (num, shown on phones too) between Filled and Result: the contracts
on offer at its price, with "+N within 1¢" muted under it, or a muted "—" when unknown. A dashboard started before this
(its orders have no "atAsk") draws the table as before. And the Filled cell says "of <asked>" on phones
(<span class="only-sm">), where the Asked column is hidden. The page is cut out with test_order_results.py's harness
and run in node (skipped without node).

    python -m pytest -q -p no:cacheprovider tests/test_orders_at_ask.py
"""

import json
import re

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, home, mode_db, order  # noqa: F401  (home is a fixture)
from test_look import RULES, norm
from test_order_results import an_order, needs_node, orders_html


def shadow(db, kind, ticker, extra, asked=15.0, filled=4.0):
    db.execute("INSERT INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price, asked, filled,"
               " lag, extra, cost, fee, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (kind, ticker, NOW - 300, NOW - 780, NOW + 120, ticker.split("-")[0], "yes", 0.94, 0.94, asked, filled,
                0.2, extra, 0.0, 0.0, "open"))


# ------------------------------------------------------------------ the server
def test_each_listed_order_gets_what_was_on_offer_at_its_ask_and_within_a_cent(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXWTI15M-A", count="69", response='{"fill_count": "0.03"}')
    order(db, NOW - 200, "KXGOLD15M-A", count="67", response='{"fill_count": "67.00"}')
    shadow(db, "fast", "KXWTI15M-A", 48.0, asked=69.0, filled=0.03)
    shadow(db, "limitup", "KXWTI15M-A", 68.97, asked=69.0, filled=0.03)
    shadow(db, "fast", "KXGOLD15M-A", 67.0, asked=67.0, filled=67.0)
    shadow(db, "limitup", "KXGOLD15M-A", 0.0, asked=67.0, filled=67.0)
    db.commit()
    got = {o["ticker"]: (o["asked"], o["filled"], o["atAsk"], o["plusOne"]) for o in dashboard.state("live-prod")["orders"]}
    assert got == {"KXWTI15M-A": (69.0, 0.03, 48.0, 68.97), "KXGOLD15M-A": (67.0, 67.0, 67.0, 0.0)}


def test_an_order_with_no_book_read_has_none(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXBTC15M-OLD")                                          # before the book reads began
    order(db, NOW - 200, "KXETH15M-HALF")
    shadow(db, "fast", "KXETH15M-HALF", 9.0)                                      # the at-ask read only
    shadow(db, "limitup", "KXSOL15M-OTHER", 5.0)                                  # another market's: not this order's
    db.commit()
    got = {o["ticker"]: (o["atAsk"], o["plusOne"]) for o in dashboard.state("live-prod")["orders"]}
    assert got == {"KXBTC15M-OLD": (None, None), "KXETH15M-HALF": (9.0, None)}


def test_a_ledger_from_before_the_book_reads_has_none_and_no_error(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXBTC15M-A")
    db.execute("DROP TABLE shadow")                                               # an older ledger: no shadow table
    db.commit()
    (o,) = dashboard.state("live-prod")["orders"]
    assert (o["atAsk"], o["plusOne"]) == (None, None)


def test_refused_and_unanswered_orders_get_the_reads_too(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXDOGE15M-A", status=400, response='{"error": {"message": "insufficient balance"}}')
    shadow(db, "fast", "KXDOGE15M-A", 30.0)
    db.commit()
    (o,) = dashboard.state("live-prod")["orders"]
    assert (o["filled"], o["atAsk"]) == (None, 30.0)


def test_the_reads_go_out_as_json_and_the_rest_of_the_order_is_unchanged(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 300, "KXBTC15M-A")
    shadow(db, "fast", "KXBTC15M-A", 12.5)
    db.commit()
    (o,) = dashboard.state("live-prod")["orders"]
    assert {k: o[k] for k in ("asked", "filled", "error", "side", "price")} == {"asked": 15.0, "filled": 4.0, "error": None,
                                                                                "side": "yes", "price": 0.93}
    json.dumps(o)


# ------------------------------------------------------------------ the page
def cells(html, row=0):
    body = html.split("<tbody>")[1]
    tr = body.split("</tr>")[row]
    return re.findall(r"<td[^>]*>.*?</td>", tr, re.S)


def heads(html):
    return re.findall(r'<th scope="col" class="([^"]*)">([^<]*)</th>', html.split("<tbody>")[0].split('class="table-wrap"')[-1])


@needs_node
def test_an_at_the_ask_column_between_filled_and_result_shown_on_phones_too():
    html = orders_html([an_order(asked=69.0, filled=0.03, atAsk=48.0, plusOne=68.97)])
    assert heads(html) == [("", "Placed"), ("", "Market"), ("", "Side · price"), ("num hide-sm", "Asked"), ("num", "Filled"),
                           ("num", "At the ask"), ("num", "Result")]
    assert len(cells(html)) == 7


@needs_node
def test_the_cell_is_whats_on_offer_at_its_price_with_whats_within_a_cent_under_it():
    html = orders_html([an_order(asked=69.0, filled=0.03, atAsk=48.0, plusOne=68.97),
                        an_order(ticker="KXGOLD15M-A", asked=67.0, filled=67.0, atAsk=67.0, plusOne=0.0)])
    assert cells(html, 0)[5] == '<td class="num">48<span class="s muted" style="display:block">+68.97 within 1¢</span></td>'
    assert cells(html, 1)[5] == '<td class="num">67<span class="s muted" style="display:block">+0 within 1¢</span></td>'


@needs_node
def test_an_unknown_read_is_a_muted_dash():
    html = orders_html([an_order(atAsk=None, plusOne=None), an_order(ticker="KXETH15M-A", atAsk=9.0, plusOne=None)])
    assert cells(html, 0)[5] == '<td class="num muted">—</td>'
    assert cells(html, 1)[5] == '<td class="num">9</td>'                          # no within-1¢ read: no line under it


@needs_node
def test_a_dashboard_from_before_draws_the_table_as_it_was():
    html = orders_html([an_order()])                                              # its orders have no atAsk
    assert [h for _, h in heads(html)] == ["Placed", "Market", "Side · price", "Asked", "Filled", "Result"]
    assert len(cells(html)) == 6 and "At the ask" not in html


@needs_node
def test_one_order_with_the_reads_brings_the_column_for_every_row():
    html = orders_html([an_order(atAsk=48.0, plusOne=1.0), an_order(ticker="KXETH15M-A")])   # the second: no key at all
    assert len(cells(html, 0)) == len(cells(html, 1)) == 7
    assert cells(html, 1)[5] == '<td class="num muted">—</td>'


@needs_node
@pytest.mark.parametrize("atask", [None, 48.0], ids=["no-read", "read"])
def test_the_filled_cell_says_of_asked_on_a_phone(atask):
    o = an_order(asked=69.0, filled=0.03, **({} if atask is None else {"atAsk": atask, "plusOne": 0.0}))
    filled = cells(orders_html([o]))[4]
    assert filled == ('<td class="num part">0.03<span class="only-sm"> of 69</span>'
                      '<span class="s muted" style="display:block">0% filled</span></td>')


@needs_node
def test_a_refused_order_still_says_of_asked_on_a_phone():
    filled = cells(orders_html([an_order(asked=15.0, filled=None, error="insufficient balance")]))[4]
    assert filled.startswith('<td class="num down">—<span class="only-sm"> of 15</span>') and "insufficient balance" in filled


def test_of_asked_shows_only_on_a_phone():
    top = [dict(r.decls) for r in RULES if r.sheet == "dashboard.html" and not r.media and any(norm(p) == ".only-sm" for p in r.parts)]
    phone = [dict(r.decls) for r in RULES if r.sheet == "dashboard.html" and "max-width: 560px" in r.media
             and any(norm(p) == ".only-sm" for p in r.parts)]
    assert top and top[-1].get("display") == "none", "no .only-sm { display: none; } for wide screens"
    assert phone and phone[-1].get("display") == "inline", "no .only-sm { display: inline; } in the 560px phone query"
