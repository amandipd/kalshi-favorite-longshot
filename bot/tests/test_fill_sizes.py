"""Fill rate by order size, on the Live tab's Orders fold: whether bigger orders fill less.

A "fill rate by order size" line on the Live tab, to see the ceiling coming (only so much is offered at 90-99c, so
past some size an order stops filling in full and growth stops compounding).

The server: dashboard.fill_sizes(orders) takes the buy orders as order_row reads them (asked, filled, error) and
buckets them by contracts asked, by SIZE_EDGES = (5, 15, 25, 35, 50, 100), the buckets' upper ends: an order goes in
the first bucket whose upper end is at or over what it asked for ("1–5" ... "51–100"), else "101+". Each bucket with an
order: {"label", "lo", "hi" (None for 101+), "orders", "asked", "filled", "none"}, smallest first. An order Kalshi
refused or never answered (filled None) says nothing about the book, so it's left out, as is one with no count.
state()["fillsBySize"] is fill_sizes over every buy order in the ledger, the orders fillsAll counts.

The page: ordersBlock() draws, only when fillsBySize has rows, a section of its own UNDER the orders table (the
timestamped orders first, the sizes after): <div class="sz">, set off
by a hairline above it, holding a heading (<h3 class="sub-h">Fills by order size</h3>), a note, and a table:
"Contracts asked" (the bucket's label: the choice the spec left to these tests, the label alone under that header,
every row alike), "Orders" (count(), with separators), "Contracts filled" (pct of asked, 0 dp, a small bar beside it
in the line's blue as long as that share, and "filled of asked" muted under it) and "Got none" (pct of orders, 0 dp).
The fold's header meta, its title count and the orders table are as before. The page is cut out with
the helpers it uses and run in node (skipped without node); one check loads the whole Live tab with
test_folds_live.py's stand-in browser.

    python -m pytest -q -p no:cacheprovider tests/test_fill_sizes.py
"""

import json
import os
import re
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, home, mode_db, order  # noqa: F401  (home is a fixture)
from test_folds_live import Tree, fold_helper, golden, missing, run
from test_look import RULES, cascade, norm, px, sides
from test_order_results import NODE, SCRIPT, needs_node, piece

DAY = 86400
KEYS = {"label", "lo", "hi", "orders", "asked", "filled", "none"}
NOTE = ("Every buy order so far, by how many contracts it asked for. If bigger orders fill less, the bot is outgrowing "
        "what's offered at 90–99¢. Orders Kalshi refused aren't counted.")


def o(asked, filled, error=None):
    """A buy order as order_row reads it."""
    return {"ts": NOW, "ticker": "KXBTC15M-A", "series": "KXBTC15M", "side": "yes", "price": 0.95,
            "asked": asked, "filled": filled, "error": error}


def bucket(label, lo, hi, orders, asked, filled, none):
    return {"label": label, "lo": lo, "hi": hi, "orders": orders, "asked": asked, "filled": filled, "none": none}


def labels(rows):
    return [r["label"] for r in rows]


# ------------------------------------------------------------------ the server: fill_sizes()
def test_the_buckets_upper_ends_are_the_specs():
    assert dashboard.SIZE_EDGES == (5, 15, 25, 35, 50, 100)


@pytest.mark.parametrize("asked, label, lo, hi", [
    (1, "1–5", 1, 5), (5, "1–5", 1, 5), (0.5, "1–5", 1, 5),
    (6, "6–15", 6, 15), (15, "6–15", 6, 15), (16, "16–25", 16, 25), (25, "16–25", 16, 25),
    (26, "26–35", 26, 35), (35, "26–35", 26, 35), (35.5, "36–50", 36, 50), (36, "36–50", 36, 50), (50, "36–50", 36, 50),
    (51, "51–100", 51, 100), (100, "51–100", 51, 100), (100.5, "101+", 101, None), (101, "101+", 101, None),
    (5000, "101+", 101, None)])
def test_an_order_goes_in_the_first_bucket_whose_upper_end_is_at_or_over_what_it_asked(asked, label, lo, hi):
    assert dashboard.fill_sizes([o(asked, 0.5)]) == [bucket(label, lo, hi, 1, asked, 0.5, 0)]


def test_labels_use_an_en_dash_and_the_last_bucket_is_101_plus():
    rows = dashboard.fill_sizes([o(a, 0.0) for a in (3, 10, 20, 30, 40, 60, 200)])
    assert labels(rows) == ["1–5", "6–15", "16–25", "26–35", "36–50", "51–100", "101+"]
    assert all("-" not in r["label"] for r in rows)                                 # an en dash, not a hyphen
    assert [(r["lo"], r["hi"]) for r in rows] == [(1, 5), (6, 15), (16, 25), (26, 35), (36, 50), (51, 100), (101, None)]
    assert all(set(r) == KEYS for r in rows)


def test_orders_asked_filled_and_none_are_summed_per_bucket():
    rows = dashboard.fill_sizes([o(15, 15.0), o(10, 4.5), o(12, 0.0), o(6, 0.0),   # 6-15: 4 orders, 2 got none
                                 o(3, 3.0), o(2, 0.5)])                            # 1-5: 2 orders, none got none
    assert rows == [bucket("1–5", 1, 5, 2, 5.0, 3.5, 0), bucket("6–15", 6, 15, 4, 43.0, 19.5, 2)]


def test_refused_and_unanswered_orders_and_ones_with_no_count_are_left_out():
    rows = dashboard.fill_sizes([o(10, None, "insufficient balance"), o(10, None, "no answer from Kalshi"),
                                 o(None, 0.0), o(None, 3.0), o(10, 2.0)])
    assert rows == [bucket("6–15", 6, 15, 1, 10.0, 2.0, 0)]


def test_empty_buckets_are_left_out_and_the_rest_come_smallest_first():
    rows = dashboard.fill_sizes([o(150, 20.0), o(3, 3.0), o(40, 40.0), o(150, 0.0), o(2, 2.0)])   # in no order
    assert rows == [bucket("1–5", 1, 5, 2, 5.0, 5.0, 0), bucket("36–50", 36, 50, 1, 40.0, 40.0, 0),
                    bucket("101+", 101, None, 2, 300.0, 20.0, 1)]


@pytest.mark.parametrize("orders", [[], [o(10, None, "insufficient balance")], [o(None, 1.0)]], ids=["none", "refused", "no-count"])
def test_with_nothing_to_count_there_are_no_buckets(orders):
    assert dashboard.fill_sizes(orders) == []


def test_it_changes_nothing_it_was_given():
    orders = [o(10, 2.0), o(None, 1.0), o(3, None, "refused")]
    before = json.dumps(orders)
    dashboard.fill_sizes(orders)
    assert json.dumps(orders) == before


# ------------------------------------------------------------------ the server: state()["fillsBySize"]
def cancel(db, ts, ticker="KXXRP15M-A"):
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (ts, ticker, "c", '{"cancel": "abc"}', 200, '{}'))


def test_the_state_buckets_every_buy_order_in_the_ledger_however_old(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 20 * DAY, "KXBTC15M-OLD", count="5", response='{"fill_count": "5.00"}')       # weeks ago: 1-5
    order(db, NOW - 90_000, "KXSOL15M-OLD", count="16", response='{"fill_count": "2.50"}')       # over a day ago: 16-25
    order(db, NOW - 300, "KXETH15M-A", response='{"fill_count": "0.00"}')                         # 15 asked, none: 6-15
    order(db, NOW - 200, "KXXRP15M-A", side="ask", price="0.0750")                                # 4 of 15: 6-15
    order(db, NOW - 150, "KXGOLD15M-A", count="120", response='{"fill_count": "33.00"}')          # 101+
    order(db, NOW - 100, "KXDOGE15M-A", status=400, response='{"error": {"message": "insufficient balance"}}')   # refused
    order(db, NOW - 90, "KXHYPE15M-A", status=None, response='"network error: timed out"')                     # unanswered
    order(db, NOW - 80, "KXBNB15M-A", status=500, response='{"detail": "oops"}')                                # a server error
    order(db, NOW - 70, "KXWTI15M-A", count=None, response='{"fill_count": "0.00"}')                            # no count
    cancel(db, NOW - 50)                                                                                         # not an order
    db.commit()
    s = dashboard.state("live-prod")
    assert s["fillsBySize"] == [bucket("1–5", 1, 5, 1, 5.0, 5.0, 0), bucket("6–15", 6, 15, 2, 30.0, 4.0, 1),
                                bucket("16–25", 16, 25, 1, 16.0, 2.5, 0), bucket("101+", 101, None, 1, 120.0, 33.0, 0)]
    left_out = 4                                                     # refused, unanswered, the server error, no count
    assert sum(b["orders"] for b in s["fillsBySize"]) == s["fillsAll"]["orders"] - left_out
    assert sum(b["filled"] for b in s["fillsBySize"]) == s["fillsAll"]["filled"]                # those filled nothing
    json.dumps(s["fillsBySize"])                                                                 # the API sends it as JSON


def test_every_order_counts_not_just_the_ones_listed(home):
    db = mode_db(home, "live-prod")
    for i in range(40):                                                                           # more than ORDERS_SHOWN
        order(db, NOW - 3 * DAY + i * 3600, f"KXBTC15M-{i:02d}")                                  # 4 of 15 each
    db.commit()
    s = dashboard.state("live-prod")
    assert len(s["orders"]) == dashboard.ORDERS_SHOWN < 40
    assert s["fillsBySize"] == [bucket("6–15", 6, 15, 40, 600.0, 160.0, 0)]


@pytest.mark.parametrize("cancels", [0, 2])
def test_with_no_buy_orders_the_state_has_no_buckets(home, cancels):
    db = mode_db(home, "live-prod")
    for i in range(cancels):
        cancel(db, NOW - 1000 * (i + 1))
    db.commit()
    assert dashboard.state("live-prod")["fillsBySize"] == []


def test_it_sits_beside_fills_all_and_the_rest_of_the_state_is_unchanged(home):
    db = mode_db(home, "live-prod")
    order(db, NOW - 100, "KXBTC15M-A")
    db.commit()
    s = dashboard.state("live-prod")
    assert s["fillsAll"] == {"orders": 1, "asked": 15.0, "filled": 4.0, "none": 0, "since": NOW - 100}
    assert s["fills"] == {"orders": 1, "asked": 15.0, "filled": 4.0, "none": 0}


# ------------------------------------------------------------------ the page: ordersBlock(), run in node
SIZES = [bucket("1–5", 1, 5, 1234, 4500.0, 3150.0, 333),          # 70% filled, 27% got none
         bucket("6–15", 6, 15, 200, 2400.0, 1248.5, 68),          # 52%, 34%
         bucket("16–25", 16, 25, 3, 60.0, 40.0, 2),               # 2/3 -> 67%, 2/3 -> 67%
         bucket("101+", 101, None, 1, 150.0, 0.0, 1)]             # 0%, 100%
FILLS = {"orders": 303, "asked": 8608, "filled": 5229.48, "none": 74}
ALL = {"orders": 720, "asked": 13760, "filled": 8013.69, "none": 193, "since": NOW - 10 * DAY}


def an_order(**more):
    return {"ts": NOW - 400, "ticker": "KXBTC15M-26SEP281500-00", "series": "KXBTC15M", "side": "yes", "price": 0.95,
            "asked": 15.0, "filled": 15.0, "error": None, "result": None, "pnl": None, "close_ts": None, **more}


def orders_html(sizes=..., orders=None):
    """What ordersBlock() writes; sizes left out = a server from before fillsBySize."""
    state = {"orders": [an_order(), an_order(ticker="KXETH15M-26SEP281500-00", filled=4.0)] if orders is None else orders,
             "fills": FILLS, "fillsAll": ALL}
    if sizes is not ...:
        state["fillsBySize"] = sizes
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
    return r.stdout


def split(html):
    """(the fold's header, up to its body's opening tag, and the body's contents)."""
    head, body = html.split('<div class="fold-body"', 1)
    attrs, inner = body.split(">", 1)
    return head + '<div class="fold-body"' + attrs + ">", inner


END = "</div></section>"   # the fold body's end, then the fold's


def size_block(html):
    """What the fill sizes add at the end of the body: the body with sizes, less the body without them (which must be
    the same orders table, unchanged, before the new block)."""
    head, inner = split(html)
    head0, inner0 = split(orders_html())
    assert head == head0, "the fold's header (its title, count and meta) changed"
    assert inner.endswith(END) and inner0.endswith(END)
    core0 = inner0[:-len(END)]
    assert inner.startswith(core0), "the orders table before the fill sizes isn't the one drawn without them"
    return inner[len(core0):-len(END)]


def size_rows(block):
    """The size table's rows: each cell's text, and the cells' elements."""
    tables = [e for e in Tree(block).root.els() if e.tag == "table"]
    assert len(tables) == 1, f"the fill sizes hold {len(tables)} tables"
    heads = [th.text() for th in tables[0].els() if th.tag == "th"]
    trs = [tr for tr in tables[0].els() if tr.tag == "tr" and tr.inside(lambda p: p.tag == "tbody")]
    return heads, [[td for td in tr.children() if td.tag == "td"] for tr in trs]


def section(block):
    """The fill sizes' one element, <div class="sz">."""
    roots = Tree(block).root.children()
    assert len(roots) == 1 and roots[0].tag == "div" and roots[0].has_class("sz"), \
        f"the fill sizes aren't one <div class=\"sz\">: {[(e.tag, e.attrs.get('class')) for e in roots]}"
    return roots[0]


@needs_node
def test_the_sizes_are_their_own_section_under_the_orders_table():
    block = size_block(orders_html(SIZES))
    kids = section(block).children()
    assert kids[0].tag == "h3" and kids[0].attrs.get("class") == "sub-h" and kids[0].text() == "Fills by order size"
    assert kids[1].tag == "p" and kids[1].text() == NOTE                          # the note, under the heading
    assert [e for e in kids[2:] if e.tag == "table" or any(x.tag == "table" for x in e.els())], "no table after the note"
    assert block.startswith('<div class="sz"><h3 class="sub-h">Fills by order size</h3>')


@needs_node
def test_the_orders_and_their_show_all_button_come_first():
    many = [{**an_order(), "ticker": f"KXBTC15M-{i:02d}"} for i in range(20)]   # over 15: the table has its Show all
    html = orders_html(SIZES, orders=many)
    assert html.index("Placed") < html.index("Show all 20") < html.index('class="sz"') < html.index("Fills by order size")


@needs_node
@pytest.mark.parametrize("sizes", [..., [], None], ids=["old-server", "empty", "null"])
def test_nothing_extra_is_drawn_without_sizes(sizes):
    html = orders_html(sizes)
    assert "Fills by order size" not in html and "sub-h" not in html and "Contracts asked" not in html
    assert html == orders_html()                                                  # exactly today's Orders fold


@needs_node
def test_the_columns_are_contracts_asked_orders_contracts_filled_and_got_none():
    heads, _ = size_rows(size_block(orders_html(SIZES)))
    assert heads == ["Contracts asked", "Orders", "Contracts filled", "Got none"]
    assert '<th scope="col" class="num">Orders</th>' in orders_html(SIZES)        # the numbers right-aligned, as Asked and Filled
    assert '<th scope="col" class="num">Contracts filled</th>' in orders_html(SIZES)
    assert '<th scope="col" class="num">Got none</th>' in orders_html(SIZES)


@needs_node
def test_each_row_is_its_bucket_smallest_first_with_its_figures():
    _, rows = size_rows(size_block(orders_html(SIZES)))
    assert [[td.text() for td in r] for r in rows] == [
        ["1–5", "1,234", "70% 3150 of 4500", "27%"],           # count()'s separators; whole contracts with no decimals
        ["6–15", "200", "52% 1248.50 of 2400", "34%"],         # a fraction to two places, as the orders table has it
        ["16–25", "3", "67% 40 of 60", "67%"],                 # 2/3 rounds up
        ["101+", "1", "0% 0 of 150", "100%"]]
    for r in rows:
        assert all("num" in td.attrs.get("class", "").split() for td in r[1:]), "a number cell isn't class num"
        subs = [e for e in r[2].els() if e.tag == "span" and e.has_class("s")]
        assert len(subs) == 1 and subs[0].has_class("muted")                       # "of" under it, muted


@needs_node
def test_the_first_column_is_the_label_alone_on_every_row():
    _, rows = size_rows(size_block(orders_html(SIZES)))
    assert [r[0].text() for r in rows] == ["1–5", "6–15", "16–25", "101+"]       # no " contracts": the header says so


@needs_node
def test_a_label_is_escaped():
    block = size_block(orders_html([bucket("<b>1–5</b>", 1, 5, 1, 5.0, 5.0, 0)]))
    assert "&lt;b&gt;1–5&lt;/b&gt;" in block and "<b>1–5</b>" not in block


@needs_node
def test_the_folds_header_title_count_and_orders_table_are_unchanged():
    size_block(orders_html(SIZES))                         # (size_block checks the header and the table after the block)
    size_block(orders_html([SIZES[0]]))


@needs_node
def test_with_no_orders_to_list_the_empty_line_still_comes_first():
    html = orders_html(SIZES, orders=[])
    assert html.index("No orders yet.") < html.index("Fills by order size")


@needs_node
def test_each_share_filled_has_a_bar_as_long_as_it_hidden_from_screen_readers():
    _, rows = size_rows(size_block(orders_html(SIZES + [bucket("51–100", 51, 100, 2, 120.0, 130.0, 0)])))   # over 100%: full
    for r, want in zip(rows, ("70%", "52%", "67%", "0%", "100%")):
        bars = [e for e in r[2].els() if e.has_class("sz-bar")]
        assert len(bars) == 1 and bars[0].attrs.get("aria-hidden") == "true", "one .sz-bar, aria-hidden, in the filled cell"
        fills = [e for e in bars[0].els() if e.tag == "i"]
        assert len(fills) == 1 and re.fullmatch(rf"width:\s*{want};?", fills[0].attrs.get("style", "").strip()), fills[0].attrs
        assert bars[0].text() == ""                                               # the bar says nothing: the % does
    assert [e for e in Tree(size_block(orders_html(SIZES))).root.els() if e.has_class("sz-bar")]


def test_the_section_is_set_off_by_a_hairline_and_its_bars_use_the_page_tokens():
    rule = lambda sel: [dict(r.decls) for r in RULES if r.sheet == "dashboard.html" and not r.media and any(norm(q) == sel for q in r.parts)]
    assert any(d.get("border-top") == "1px solid var(--line)" for d in rule(".sz")), "no .sz { border-top: 1px solid var(--line); }"
    bar, fill = rule(".sz-bar"), rule(".sz-bar i")
    assert bar and fill, "no .sz-bar / .sz-bar i rules"
    track = {k: v for d in bar for k, v in d.items()}
    assert track.get("background") in ("var(--surface-2)", "var(--line)", "var(--hover)")
    assert track.get("border-radius") == "var(--r-pill)" and 4 <= px(track.get("height")) <= 8
    assert {k: v for d in fill for k, v in d.items()}.get("background") == "var(--series-1)"    # the Fill rate line's blue


# ------------------------------------------------------------------ the whole Live tab, and its look
@needs_node
def test_the_live_tab_adds_the_sizes_to_the_orders_fold_and_loses_no_word():
    g = golden()
    page = run(inputs={**g, "state": {**g["state"], "fillsBySize": SIZES}})[0]
    body = page.fold("live.orders").body.text()
    assert "Fills by order size" in body and NOTE in body and "1,234" in body
    assert not missing(page), f"words of today's Live tab are gone: {missing(page)}"


def test_the_heading_and_the_note_start_on_the_folds_16px_edge_with_page_tokens():
    sub = [r for r in RULES if r.sheet == "dashboard.html" and any(p.strip() == ".sub-h" for p in r.parts)]
    assert sub, "dashboard.html has no .sub-h rule"
    pad = sides(cascade([".sub-h"]))
    assert (px(pad.get("left")), px(pad.get("right"))) == (16, 16), pad            # in line with the fold's title
    raw = [(r.selector, k, v) for r in sub for k, v in r.decls if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", v)]
    assert not raw, raw


@needs_node
def test_the_note_is_on_the_16px_edge_too():
    note = section(size_block(orders_html(SIZES))).children()[1]
    cls = note.attrs.get("class", "").split()
    assert cls, "the note has no class to style it with"
    pad = sides(cascade(["." + c for c in cls]))
    assert (px(pad.get("left")), px(pad.get("right"))) == (16, 16), pad
