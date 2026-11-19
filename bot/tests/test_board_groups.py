"""dashboard.html's boardBlock(): the Live tab's market board, one table per asset class, two side by side.

Live markets, two asset classes per row instead of one. The board
still shows only the bot's groups (`data.groups`), but each group (crypto, metals, energy, then any other in name order)
now gets its own small header, `<h3 class="bd-gh">Crypto <span class="n">5</span></h3>`, and its own table, with
the rows sorted inside it (highest favorite price first, ties by name, no price last). With two or more groups the
groups are placed, in that order, into two columns (`.bd-cols` > two `.bd-col`): each goes to the column with fewer
rows so far, a group counting its markets + 2 (its header and its table's header), a tie going left. One group is
drawn alone, full width. The per-row group tag (`.bd-grp`) goes, since the header names the group. Every row is
otherwise byte for byte what today's board draws (ROWS below). From 900px wide every group's table (`.bd-g .bd-t`)
lays out fixed with the same seven column widths, so the groups' columns line up whether they stack, sit side by side
or stand alone; under 900px the tables keep the auto layout (a phone hides the hide-sm columns). From 1360px wide
the two columns sit side by side (one column below that), the sparkline shrinking to fit its column and a long name's
"In range" tag wrapping under it. (900px, 1360px and the widths were settled after screenshots.)

boardBlock() is cut out of the page with the helpers it uses (as test_live_board.py does) and run in node, one draw
or several in a row in one process (so a price change between draws flashes its row, as the page's one-second
redraw does); a few checks load the whole Live tab instead (test_folds_live.py's stand-in browser and fixed data).
The CSS is read with test_look.py's parser. The tests skip themselves without node.

    python -m pytest -q -p no:cacheprovider tests/test_board_groups.py
"""

import json
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_folds_live import Tree, fold_helper, golden, run
from test_look import RULES, applies_at, norm

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")

WINDOW = 1_791_599_400          # a window's start: a multiple of 900 s
NOW = WINDOW + 3 * 60 + 30      # minute 4, before the bot's entry at minute 8: "In range" shows
WIDE = "(min-width: 1360px)"   # under 1360px a favorite like "YES 98.8¢ ▲" won't fit
FIXED = "(min-width: 900px)"    # every group's table the same columns from here up, stacked or side by side
NARROW = (899, 768, 600, 560, 480, 375)   # widths where the tables keep the auto layout
THEAD = ('<thead><tr><th scope="col">Market</th><th scope="col" aria-sort="descending">Favorite ↓</th>'
         '<th scope="col" class="hide-sm">Bid</th><th scope="col" class="hide-sm">Ask</th><th scope="col" class="hide-sm">Spread</th>'
         '<th scope="col">This window</th><th scope="col" class="hide-sm">Trend</th></tr></thead>')


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def harness():
    return "\n".join([
        piece(r"^const esc = .*?;$"), piece(r"^const zero = .*?;$"), piece(r"^const tone = .*?;$"), piece(r"^const cents = .*?;$"),
        piece(r"^const kalshiUrl = .*?^\};$"),
        piece(r"^const BOARD_FRESH = .*?;"), piece(r"^const BOARD_GROUPS = .*?;"), piece(r"^const lastFav = .*?;"),
        piece(r"^function flashOf\(m\) \{.*?^\}$"), piece(r"^function sparkOf\(m\) \{.*?^\}$"), piece(r"^function boardBlock\(\) \{.*?^\}$"),
        fold_helper(HTML),
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "const LIMITS = { lo: 0.9, hi: 0.999, minute: 8 };",
        "let board = null, boardErr = false, data = null, nowS = null, out = {};",
        "const patch = (id, h) => { out[id] = h; return true; };",
        "const draws = [];",
        "for (const d of input) { board = d.board; boardErr = d.err; data = d.data; nowS = () => d.now; out = {};"
        " boardBlock(); draws.push(Object.values(out).join('')); }",
        "process.stdout.write(JSON.stringify(draws));",
    ])


def climb(start, end, spread=0.01):
    """A minute-by-minute path, minutes 0 to 3, from one mid to another."""
    return [[m, round(start + (end - start) * m / 3, 4), round(start + (end - start) * m / 3 + spread, 4)] for m in range(4)]


def mk(label, group, bid, ask, path=()):
    """One market as /api/research/live sends it: the favorite is the side that costs more."""
    if ask is None:
        fav = price = None
    else:
        fav = "yes" if (bid + ask) / 2 >= 0.5 else "no"
        price = ask if fav == "yes" else round(1 - bid, 4)
    return {"ticker": f"KX{label}15M-26OCT131515-15", "label": label, "group": group, "yes_bid": bid, "yes_ask": ask,
            "last": ask, "favSide": fav, "favPrice": price, "path": list(path)}


def frame(markets, groups=("crypto", "metals", "energy"), now=NOW, live=True, err=False):
    lv = {"heartbeat": "2026-10-13T19:18:28Z", "source": "stream", "band": [0.9, 0.999], "markets": list(markets)}
    return {"now": now, "err": err, "board": {"live": lv} if live else None,
            "data": {"groups": list(groups), "limits": {"minute": 8}}}


def draws(*frames):
    if not NODE:
        pytest.skip("node isn't installed")
    r = subprocess.run([NODE, "-e", harness()], input=json.dumps(list(frames)), capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def draw(markets, **kw):
    return draws(frame(markets, **kw))[0]


def many(group, n, top=0.98):
    """n markets of one group, each a cent cheaper than the last."""
    tag = group[:3].upper()
    return [mk(f"{tag}{i}", group, round(top - 0.01 * i - 0.01, 4), round(top - 0.01 * i, 4)) for i in range(n)]


# ------------------------------------------------------------------ reading the board
def els(html):
    return list(Tree(html).root.els())


def group_of(g):
    """One .bd-g: (name, count, the labels of its rows top to bottom), after checking its shape: a header h3.bd-gh (the
    name, then the count in span.n), then a .bd-wrap holding one table.bd-t."""
    kids = g.children()
    assert len(kids) == 2, f".bd-g should hold a header and a .bd-wrap, holds {[k.tag for k in kids]}"
    h, wrap = kids
    assert h.tag == "h3" and h.has_class("bd-gh"), f"a group starts with <{h.tag} class={h.attrs.get('class')!r}>"
    ns = [e for e in h.els() if e.tag == "span" and e.has_class("n")]
    assert len(ns) == 1, f"the header {h.text()!r} has no count in <span class=\"n\">"
    assert wrap.tag == "div" and wrap.has_class("bd-wrap"), f"the header is followed by <{wrap.tag} class={wrap.attrs.get('class')!r}>"
    tables = [e for e in wrap.els() if e.tag == "table"]
    assert len(tables) == 1 and tables[0].has_class("bd-t"), "each group's .bd-wrap holds one table.bd-t"
    name = " ".join(s.strip() for s in h.kids if isinstance(s, str) and s.strip())
    return name, ns[0].text(), [a.text() for a in tables[0].els() if a.tag == "a" and a.has_class("bd-mk")]


def groups(html):
    """Each .bd-g in page order, as group_of reads it."""
    return [group_of(g) for g in els(html) if g.has_class("bd-g")]


def names(html):
    return [g[0] for g in groups(html)]


def columns_of(root):
    """The groups' names in each .bd-col, left to right (None with no .bd-cols), after checking the shape: one .bd-cols
    holding only .bd-col divs, each holding only .bd-g groups, at least one."""
    cols = [e for e in root.els() if e.has_class("bd-cols")]
    if not cols:
        assert not [e for e in root.els() if e.has_class("bd-col")], "a .bd-col outside .bd-cols"
        return None
    assert len(cols) == 1, f"{len(cols)} .bd-cols on the board"
    out = []
    for c in cols[0].children():
        assert c.tag == "div" and c.has_class("bd-col"), f".bd-cols holds a <{c.tag} class={c.attrs.get('class')!r}>"
        assert c.children() and all(g.has_class("bd-g") for g in c.children()), "a .bd-col holds only .bd-g groups, at least one"
        out.append([group_of(g)[0] for g in c.children()])
    return out


def columns(html):
    return columns_of(Tree(html).root)


def rows(html):
    """Each drawn row's markup, by its market's label."""
    trs = re.findall(r'<tr class="bd-r.*?</tr>', html)
    return {re.search(r'title="([^"]+) on Kalshi"', tr).group(1): tr for tr in trs}


# ------------------------------------------------------------------ groups and order
@needs_node
def test_with_crypto_metals_and_energy_open_there_are_three_groups_in_that_order():
    html = draw([*many("energy", 1), *many("metals", 2), *many("crypto", 3)])   # sent energy first, crypto last
    assert names(html) == ["Crypto", "Metals", "Energy"]
    assert [(n, c) for n, c, _ in groups(html)] == [("Crypto", "3"), ("Metals", "2"), ("Energy", "1")]


@needs_node
def test_each_group_has_its_header_with_its_name_and_count_then_its_own_table():
    html = draw([*many("crypto", 3), *many("metals", 2), *many("energy", 1)])
    for name, n in (("Crypto", 3), ("Metals", 2), ("Energy", 1)):
        assert f'<h3 class="bd-gh">{name} <span class="n">{n}</span></h3>' in html
    assert html.count('<table class="bd-t">') == 3 and html.count(THEAD) == 3   # each table keeps today's header row
    assert html.count('<th scope="col" aria-sort="descending">Favorite ↓</th>') == 3


@needs_node
def test_groups_the_page_has_no_name_for_come_after_in_name_order_under_their_own_name():
    html = draw([mk("RAIN", "weather", 0.95, 0.96), mk("CORN", "agri", 0.95, 0.96), mk("WTI", "energy", 0.95, 0.96),
                 mk("BTC", "crypto", 0.95, 0.96)], groups=("crypto", "weather", "energy", "agri"))
    assert columns(html) == [["Crypto", "agri"], ["Energy", "weather"]]   # crypto, energy, agri, weather; 3 rows each
    assert '<h3 class="bd-gh">agri <span class="n">1</span></h3>' in html


@needs_node
def test_a_group_name_the_page_has_no_label_for_is_escaped():
    html = draw([mk("GAS", "oil & <gas>", 0.95, 0.96)], groups=("oil & <gas>",))
    assert '<h3 class="bd-gh">oil &amp; &lt;gas&gt; <span class="n">1</span></h3>' in html


@needs_node
def test_rows_sort_within_each_group_highest_first_ties_by_name_no_price_last():
    html = draw([mk("BTC", "crypto", 0.63, 0.64), mk("ZEC", "crypto", None, None), mk("XRP", "crypto", 0.02, 0.03),   # XRP: NO 98c
                 mk("GOLD", "metals", 0.96, 0.97), mk("DOGE", "crypto", 0.69, 0.70), mk("ETH", "crypto", 0.79, 0.80),
                 mk("COPPER", "metals", None, None), mk("BNB", "crypto", 0.69, 0.70), mk("SILVER", "metals", 0.90, 0.91),
                 mk("WTI", "energy", 0.87, 0.88), mk("NATGAS", "energy", 0.01, 0.02)])                                # NATGAS: NO 99c
    assert [(n, labels) for n, _, labels in groups(html)] == [
        ("Crypto", ["XRP", "ETH", "BNB", "DOGE", "BTC", "ZEC"]),   # 98, 80, 70, 70 (by name), 64, no price
        ("Metals", ["GOLD", "SILVER", "COPPER"]),                  # GOLD's 97c doesn't put it among the crypto rows
        ("Energy", ["NATGAS", "WTI"])]


@needs_node
def test_the_order_inside_a_group_follows_the_prices_on_every_read():
    first, then = draws(frame([mk("BTC", "crypto", 0.90, 0.91), mk("ETH", "crypto", 0.70, 0.71), mk("GOLD", "metals", 0.95, 0.96)]),
                        frame([mk("BTC", "crypto", 0.60, 0.61), mk("ETH", "crypto", 0.95, 0.96), mk("GOLD", "metals", 0.95, 0.96)]))
    assert [labels for _, _, labels in groups(first)] == [["BTC", "ETH"], ["GOLD"]]
    assert [labels for _, _, labels in groups(then)] == [["ETH", "BTC"], ["GOLD"]]   # a second later ETH has passed BTC


@needs_node
def test_coin_race_and_any_group_the_bot_doesnt_trade_are_still_left_out():
    html = draw([*many("crypto", 2), *many("metals", 1), mk("RACE", "coin race", 0.98, 0.99), mk("RAIN", "weather", 0.98, 0.99)])
    assert names(html) == ["Crypto", "Metals"] and "RACE" not in html and "RAIN" not in html
    assert "coin race" not in html.lower() and "weather" not in html
    assert 'Live markets <span class="n">3</span>' in html


@needs_node
def test_a_traded_group_with_no_market_open_gets_no_header():
    html = draw([*many("crypto", 2), *many("energy", 1)])   # metals is traded but has nothing open
    assert names(html) == ["Crypto", "Energy"] and "Metals" not in html


@needs_node
def test_no_row_carries_a_group_tag_any_more():
    html = draw([*many("crypto", 2), *many("metals", 2), *many("energy", 2)])
    assert "bd-grp" not in html
    for label, tr in rows(html).items():
        assert ">Crypto<" not in tr and ">Metals<" not in tr and ">Energy<" not in tr, label


def test_the_group_tag_is_gone_from_the_page_its_css_and_its_phone_rule():
    assert "bd-grp" not in HTML, "dashboard.html still has .bd-grp (a CSS rule, the phone rule or the script)"


# ------------------------------------------------------------------ two columns, balanced
@needs_node
@pytest.mark.parametrize("sizes, want", [
    ({"crypto": 9, "metals": 5, "energy": 2}, [["Crypto"], ["Metals", "Energy"]]),   # the spec's first example
    ({"crypto": 9, "energy": 2}, [["Crypto"], ["Energy"]]),                         # its second
    ({"crypto": 1, "metals": 6, "energy": 2}, [["Crypto", "Energy"], ["Metals"]]),   # left 3, right 8: energy goes left
    ({"crypto": 2, "metals": 2, "energy": 2}, [["Crypto", "Energy"], ["Metals"]]),   # 4 rows each side: a tie goes left
    ({"metals": 3, "energy": 3}, [["Metals"], ["Energy"]]),                         # no crypto (never on a weekday, but)
    ({"crypto": 4, "metals": 1, "energy": 1, "agri": 1},                            # 6 | 3, then 6 | 6: agri ties, left
     [["Crypto", "agri"], ["Metals", "Energy"]]),                                    # (by markets alone, 4 | 3: right)
], ids=["9-5-2", "9-0-2", "1-6-2", "2-2-2", "0-3-3", "4-1-1-1"])
def test_groups_go_in_order_to_the_column_with_fewer_rows_so_far(sizes, want):
    markets = [m for g, n in reversed(list(sizes.items())) for m in many(g, n)]   # sent in reverse: the page orders them
    html = draw(markets, groups=list(sizes))
    assert columns(html) == want
    assert html.count('class="bd-col"') == 2 and html.count('class="bd-cols"') == 1


@needs_node
def test_one_group_open_draws_its_header_and_table_alone_full_width():
    html = draw(many("crypto", 4))   # a weekend: crypto only
    assert columns(html) is None and "bd-col" not in html
    assert [(n, c, len(labels)) for n, c, labels in groups(html)] == [("Crypto", "4", 4)]


@needs_node
@pytest.mark.parametrize("kw, line", [
    ({}, "None of the bot's markets is open right now."),
    ({"live": False}, "Connecting to Kalshi's live markets…"),
    ({"err": True}, "Can't reach the dashboard's server."),
], ids=["none-open", "connecting", "offline"])
def test_no_markets_shows_the_same_empty_line_as_before(kw, line):
    html = draw([], **kw)
    assert f'<div class="bd-wrap"><p class="bd-empty">{line}</p></div>' in html
    assert not any(c in html for c in ('class="bd-g"', "bd-gh", "bd-col", "<table"))
    assert 'Live markets <span class="n">0</span>' in html


@needs_node
def test_only_markets_the_bot_doesnt_trade_is_no_markets_too():
    html = draw([mk("RACE", "coin race", 0.98, 0.99)])
    assert '<p class="bd-empty">None of the bot\'s markets is open right now.</p>' in html and "bd-g" not in html


# ------------------------------------------------------------------ rows and the fold's header unchanged
MARKETS = [mk("BTC", "crypto", 0.95, 0.96, climb(0.80, 0.95)), mk("ETH", "crypto", 0.06, 0.07, climb(0.30, 0.06)),   # NO at 94c
           mk("SOL", "crypto", 0.71, 0.72, climb(0.62, 0.71)), mk("DOGE", "crypto", None, None),                     # no price
           mk("GOLD", "metals", 0.91, 0.93, climb(0.85, 0.91, 0.02)), mk("WTI", "energy", 0.40, 0.42, climb(0.52, 0.40, 0.02))]
# Each row as today's board (before the split) drew it from MARKETS at NOW, with its group tag taken out: the link,
# "In range" and its edge, the pill and price, bid, ask, spread, the change and the sparkline, the muted dashes.
ROWS = {
    'BTC': ('<tr class="bd-r in"><td><a class="bd-mk" href="https://kalshi.com/markets/kxbtc15m/kxbtc15m/kxbtc15m-26oct1315'
            '15" target="_blank" rel="noopener" title="BTC on Kalshi">BTC</a><span class="bd-in" title="In the bot\'s 90¢–99'
            '.9¢ buying range">In range</span></td><td><span class="bd-fav"><span class="pill yes">YES</span><span class="b'
            'd-px">96¢</span></span></td><td class="hide-sm">95¢</td><td class="hide-sm">96¢</td><td class="hide-sm">1¢</td'
            '><td class="up">▲ 15.0¢</td><td class="hide-sm"><svg class="bd-spark" viewBox="0 0 84 20" aria-hidden="true"><'
            'path d="M1.0 18.5L6.5 12.8L11.9 7.2L17.4 1.5L20.1 1.5"/><circle cx="20.1" cy="1.5" r="1.8"/></svg></td></tr>'),
    'ETH': ('<tr class="bd-r in"><td><a class="bd-mk" href="https://kalshi.com/markets/kxeth15m/kxeth15m/kxeth15m-26oct1315'
            '15" target="_blank" rel="noopener" title="ETH on Kalshi">ETH</a><span class="bd-in" title="In the bot\'s 90¢–99'
            '.9¢ buying range">In range</span></td><td><span class="bd-fav"><span class="pill no">NO</span><span class="bd-'
            'px">94¢</span></span></td><td class="hide-sm">93¢</td><td class="hide-sm">94¢</td><td class="hide-sm">1¢</td><'
            'td class="up">▲ 24.0¢</td><td class="hide-sm"><svg class="bd-spark" viewBox="0 0 84 20" aria-hidden="true"><pa'
            'th d="M1.0 18.5L6.5 12.8L11.9 7.2L17.4 1.5L20.1 1.5"/><circle cx="20.1" cy="1.5" r="1.8"/></svg></td></tr>'),
    'GOLD': ('<tr class="bd-r in"><td><a class="bd-mk" href="https://kalshi.com/markets/kxgold15m/kxgold15m/kxgold15m-26oct1'
            '31515" target="_blank" rel="noopener" title="GOLD on Kalshi">GOLD</a><span class="bd-in" title="In the bot\'s 9'
            '0¢–99.9¢ buying range">In range</span></td><td><span class="bd-fav"><span class="pill yes">YES</span><span cla'
            'ss="bd-px">93¢</span></span></td><td class="hide-sm">91¢</td><td class="hide-sm">93¢</td><td class="hide-sm">2'
            '¢</td><td class="up">▲ 6.0¢</td><td class="hide-sm"><svg class="bd-spark" viewBox="0 0 84 20" aria-hidden="tru'
            'e"><path d="M1.0 15.1L6.5 11.7L11.9 8.3L17.4 4.9L20.1 4.9"/><circle cx="20.1" cy="4.9" r="1.8"/></svg></td></t'
            'r>'),
    'SOL': ('<tr class="bd-r"><td><a class="bd-mk" href="https://kalshi.com/markets/kxsol15m/kxsol15m/kxsol15m-26oct131515"'
            ' target="_blank" rel="noopener" title="SOL on Kalshi">SOL</a></td><td><span class="bd-fav"><span class="pill y'
            'es">YES</span><span class="bd-px">72¢</span></span></td><td class="hide-sm">71¢</td><td class="hide-sm">72¢</t'
            'd><td class="hide-sm">1¢</td><td class="up">▲ 9.0¢</td><td class="hide-sm"><svg class="bd-spark" viewBox="0 0 '
            '84 20" aria-hidden="true"><path d="M1.0 17.6L6.5 12.5L11.9 7.4L17.4 2.3L20.1 2.3"/><circle cx="20.1" cy="2.3" '
            'r="1.8"/></svg></td></tr>'),
    'WTI': ('<tr class="bd-r"><td><a class="bd-mk" href="https://kalshi.com/markets/kxwti15m/kxwti15m/kxwti15m-26oct131515"'
            ' target="_blank" rel="noopener" title="WTI on Kalshi">WTI</a></td><td><span class="bd-fav"><span class="pill n'
            'o">NO</span><span class="bd-px">60¢</span></span></td><td class="hide-sm">58¢</td><td class="hide-sm">60¢</td>'
            '<td class="hide-sm">2¢</td><td class="up">▲ 12.0¢</td><td class="hide-sm"><svg class="bd-spark" viewBox="0 0 8'
            '4 20" aria-hidden="true"><path d="M1.0 18.5L6.5 12.8L11.9 7.2L17.4 1.5L20.1 1.5"/><circle cx="20.1" cy="1.5" r'
            '="1.8"/></svg></td></tr>'),
    'DOGE': ('<tr class="bd-r"><td><a class="bd-mk" href="https://kalshi.com/markets/kxdoge15m/kxdoge15m/kxdoge15m-26oct1315'
            '15" target="_blank" rel="noopener" title="DOGE on Kalshi">DOGE</a></td><td class="muted">—</td><td class="hide'
            '-sm muted">—</td><td class="hide-sm muted">—</td><td class="hide-sm muted">—</td><td class="muted">—</td><td c'
            'lass="hide-sm"><svg class="bd-spark" viewBox="0 0 84 20" aria-hidden="true"></svg></td></tr>'),
}


@needs_node
def test_each_rows_markup_is_todays_without_its_group_tag():
    assert rows(draw(MARKETS)) == ROWS


@needs_node
def test_a_rows_markup_is_the_same_whether_its_group_is_alone_or_not():
    alone = rows(draw([m for m in MARKETS if m["group"] == "crypto"]))
    assert alone == {k: v for k, v in ROWS.items() if k in ("BTC", "ETH", "SOL", "DOGE")}


@needs_node
def test_a_price_change_between_reads_still_flashes_its_row_in_any_group():
    before = [mk("BTC", "crypto", 0.95, 0.96), mk("GOLD", "metals", 0.91, 0.93), mk("WTI", "energy", 0.04, 0.05)]
    after = [mk("BTC", "crypto", 0.95, 0.96), mk("GOLD", "metals", 0.93, 0.94), mk("WTI", "energy", 0.97, 0.98)]
    first, then, still = (rows(h) for h in draws(frame(before), frame(after), frame(after)))
    assert all(" fl-" not in tr for tr in first.values())                        # the first read: nothing to compare with
    assert 'class="bd-r in fl-up"' in then["GOLD"] and '<i class="bd-tick up">▲</i>' in then["GOLD"]   # 93c -> 94c
    assert 'class="bd-r in fl-flip"' in then["WTI"] and "⇄</i>" in then["WTI"]    # NO 96c -> YES 98c
    assert " fl-" not in then["BTC"]                                              # unchanged: no flash
    assert all(" fl-" not in tr for tr in still.values())                        # and once only


@needs_node
def test_the_folds_title_counts_every_market_of_every_group():
    html = draw([*many("crypto", 9), *many("metals", 5), *many("energy", 2), mk("RACE", "coin race", 0.98, 0.99)])
    assert 'Live markets <span class="n">16</span>' in html


@needs_node
def test_the_folds_status_meta_is_unchanged():
    html = draw([*many("crypto", 2), *many("metals", 1)])
    assert ('<span class="bd-status" title="Prices stream from Kalshi as they change"><span class="pulse on" aria-hidden="true">'
            '</span>Streaming · minute 4 of 15</span>') in html


@needs_node
def test_the_live_tab_draws_the_groups_from_its_fixed_data():
    """The whole page, not the board alone: test_folds_live.py's data has five crypto markets, one metals, one energy
    and a Coin Race market the bot doesn't trade."""
    page = run()[0]
    body = page.fold("live.board").body
    gs = [group_of(g) for g in body.els() if g.has_class("bd-g")]
    assert [(n, c, len(labels)) for n, c, labels in gs] == [("Crypto", "5", 5), ("Metals", "1", 1), ("Energy", "1", 1)]
    assert columns_of(body) == [["Crypto"], ["Metals", "Energy"]]   # 7 rows | 3, then 3 < 7
    assert "RACE" not in body.text() and golden()["headers"]["live.board"]["count"] in page.fold("live.board").title.split()


# ------------------------------------------------------------------ CSS (read with test_look.py's parser)
def rules(selector, media=""):
    """The declarations of every dashboard.html rule whose selector list holds `selector` (normalised), under `media`."""
    sel = norm(selector)
    return [dict(r.decls) for r in RULES if r.sheet == "dashboard.html" and r.media == media and any(norm(p) == sel for p in r.parts)]


def decl(selector, prop, media=""):
    vals = [d[prop] for d in rules(selector, media) if prop in d]
    assert vals, f"no {selector} rule{' in @media ' + media if media else ''} sets {prop}"
    return vals[-1]


RAW_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(|\b(?:white|black|gr[ae]y|silver)\b")


def test_bd_cols_is_one_grid_column_by_default():
    assert decl(".bd-cols", "display") == "grid"
    assert decl(".bd-cols", "grid-template-columns") == "minmax(0, 1fr)"


def test_from_1360px_wide_bd_cols_is_two_equal_columns_split_by_a_left_hairline():
    assert decl(".bd-cols", "grid-template-columns", WIDE) == "repeat(2, minmax(0, 1fr))"
    assert decl(".bd-col + .bd-col", "border-left", WIDE) == "1px solid var(--line)"
    assert decl(".bd-col + .bd-col", "border-top", WIDE) in ("0", "none", "0px")   # side by side: no top hairline


def test_no_narrower_screen_gets_two_columns():
    two = [r for r in RULES if r.media != WIDE and any("bd-col" in p for p in r.parts)
           and any(p == "grid-template-columns" and "repeat(2" in v for p, v in r.decls)]
    assert not two, f"two board columns outside {WIDE}: {[(r.media, r.selector) for r in two]}"


def test_stacked_groups_and_stacked_columns_are_split_by_a_top_hairline():
    assert decl(".bd-col > .bd-g + .bd-g", "border-top") == "1px solid var(--line)"
    assert decl(".bd-col + .bd-col", "border-top") == "1px solid var(--line)"


def board_rules():
    """dashboard.html's rules on the board's tables: a selector naming .bd-g, .bd-t, .bd-col(s) or .bd-wrap."""
    return [r for r in RULES if r.sheet == "dashboard.html" and any(re.search(r"\.bd-(?:g|t|cols?|wrap)\b", p) for p in r.parts)]


def test_from_900px_every_group_table_lays_out_fixed_so_the_groups_columns_line_up():
    assert decl(".bd-g .bd-t", "table-layout", FIXED) == "fixed"
    assert decl(".bd-g .bd-t", "width", FIXED) == "100%"


def test_from_900px_the_seven_columns_take_the_same_widths_in_every_group():
    got = {}
    for r in RULES:
        if r.sheet == "dashboard.html" and r.media == FIXED:
            for p in r.parts:
                m = re.fullmatch(r"\.bd-g \.bd-t th:nth-child\((\d)\)", norm(p))
                if m and "width" in dict(r.decls):
                    got[int(m.group(1))] = dict(r.decls)["width"]
    assert got == {1: "24%", 2: "19%", 3: "9%", 4: "9%", 5: "10%", 6: "14%", 7: "15%"}   # the widths, settled after screenshots


@pytest.mark.parametrize("width", NARROW)
def test_under_900px_the_board_tables_keep_the_auto_layout_and_no_fixed_widths(width):
    fixed = [(r.media, r.selector) for r in board_rules() if applies_at(r.media, width)
             and dict(r.decls).get("table-layout") == "fixed"]
    assert not fixed, f"a fixed table layout reaches the board at {width}px: {fixed}"
    widths = [(r.media, r.selector) for r in board_rules() if applies_at(r.media, width) and "width" in dict(r.decls)
              and any("th:nth-child" in p for p in r.parts)]
    assert not widths, f"column widths reach the board at {width}px: {widths}"


def test_side_by_side_the_sparkline_shrinks_to_fit_its_column():
    """The sparkline is 84px wide; a Trend column is narrower than that until the page is about 1,700px wide, so inside
    the columns it takes its cell's width, at most 84px (its viewBox scales). One column, it keeps its 84px."""
    assert decl(".bd-cols .bd-spark", "width", WIDE) == "100%"
    assert decl(".bd-cols .bd-spark", "max-width", WIDE) == "84px"
    assert not rules(".bd-cols .bd-spark"), "the sparkline shrinks only side by side, in the 1360px query"


def test_side_by_side_a_long_names_in_range_tag_wraps_under_it():
    assert decl(".bd-cols .bd-t td:first-child", "white-space", WIDE) == "normal"
    assert not rules(".bd-cols .bd-t td:first-child"), "the market cell wraps only side by side, in the 1360px query"


def test_the_group_header_uses_the_page_tokens_only():
    want = {"margin": "0", "padding": "var(--sp-2) var(--sp-4)", "font": "600 var(--fs-2)/20px var(--sans)",
            "color": "var(--ink-2)", "border-bottom": "1px solid var(--line)"}
    assert {k: decl(".bd-gh", k) for k in want} == want
    assert decl(".bd-gh .n", "color") == "var(--muted)" and decl(".bd-gh .n", "font-weight") == "400"
    raw = [(r.selector, k, v) for r in RULES if r.sheet == "dashboard.html" for p in r.parts
           if re.search(r"\.bd-(?:gh|g|cols?)\b", p) for k, v in r.decls if RAW_COLOUR.search(v)]
    assert not raw, f"raw colours in the board's group rules: {raw}"
