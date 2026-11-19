"""dashboard.html's boardBlock(): the Live tab's market board, run for real in node.

The board and the page helpers it leans on (esc, zero, tone, cents, kalshiUrl, flashOf, sparkOf, the board's
constants, and the shared fold helper it draws through once the Live tab folds) are cut out of the page
itself; patch() is stood in for so a test reads the HTML the board drew (every region it wrote). Each read redraws the
board, so what's checked here is what every one-second redraw does: the bot's markets only, highest favorite price
first within each asset class (each class under its own header, two side by side: test_board_groups.py). The tests
skip themselves without node.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_folds_live import fold_helper

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node isn't installed")


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


HARNESS = "\n".join([
    piece(r"^const esc = .*?;$"), piece(r"^const zero = .*?;$"), piece(r"^const tone = .*?;$"), piece(r"^const cents = .*?;$"),
    piece(r"^const kalshiUrl = .*?^\};$"),   # each market's name links to it on Kalshi
    piece(r"^const BOARD_FRESH = .*?;"), piece(r"^const BOARD_GROUPS = .*?;"), piece(r"^const lastFav = .*?;"),
    piece(r"^function flashOf\(m\) \{.*?^\}$"), piece(r"^function sparkOf\(m\) \{.*?^\}$"), piece(r"^function boardBlock\(\) \{.*?^\}$"),
    fold_helper(HTML),   # the board draws inside a fold once the Live tab folds (empty before that)
    "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
    "const nowS = () => input.now, LIMITS = { lo: 0.9, hi: 0.999 }, data = { groups: ['crypto', 'metals', 'energy'] };",
    "let board = input.board, boardErr = false;",
    "const out = {}, patch = (id, h) => { out[id] = h; return true; };",
    "boardBlock();",
    "process.stdout.write(Object.values(out).join(''));",
])
NOW = 1_791_600_000 + 7 * 60   # minute 8 of a window


def market(label, group, bid, ask, ticker=None):
    return {"ticker": ticker or f"KX{label}15M-A", "label": label, "group": group, "yes_bid": bid, "yes_ask": ask,
            "favSide": None if ask is None else ("yes" if ask >= 0.5 else "no"),
            "favPrice": None if ask is None else (ask if ask >= 0.5 else round(1 - bid, 4)), "path": []}


def draw(*markets):
    live = {"heartbeat": "2026-10-10T09:00:00Z", "source": "stream", "band": [0.9, 0.999], "markets": list(markets)}
    r = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"now": NOW, "board": {"live": live}}),
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def order(html):
    """The markets' names, top to bottom."""
    return re.findall(r'class="bd-mk"[^>]*>([^<]*)<', html)


def test_the_board_lists_the_highest_favorite_price_first():
    html = draw(market("BTC", "crypto", 0.63, 0.64), market("XRP", "crypto", 0.02, 0.03),   # XRP: NO at 98c
                market("ETH", "crypto", 0.79, 0.80), market("SOL", "crypto", 0.44, 0.45))  # SOL: NO at 56c
    assert order(html) == ["XRP", "ETH", "BTC", "SOL"]                                      # 98c, 80c, 64c, 56c


def test_the_order_follows_the_prices_on_every_read():
    first = draw(market("BTC", "crypto", 0.90, 0.91), market("ETH", "crypto", 0.70, 0.71))
    then = draw(market("BTC", "crypto", 0.60, 0.61), market("ETH", "crypto", 0.95, 0.96))   # a second later: ETH has passed BTC
    assert (order(first), order(then)) == (["BTC", "ETH"], ["ETH", "BTC"])


def test_a_market_with_no_price_yet_sorts_last_and_ties_go_by_name():
    html = draw(market("ZEC", "crypto", None, None), market("DOGE", "crypto", 0.69, 0.70), market("BNB", "crypto", 0.69, 0.70))
    assert order(html) == ["BNB", "DOGE", "ZEC"]


def test_the_board_keeps_to_the_bots_groups_each_under_its_own_header():
    """Superseded by the board's groups (test_board_groups.py): no longer one order across groups with a tag on each row, but one table per
    group under a header naming it (the order and the columns: test_board_groups.py)."""
    html = draw(market("GOLD", "metals", 0.96, 0.97), market("BTC", "crypto", 0.80, 0.81),
                market("WTI", "energy", 0.88, 0.89), market("RACE", "coin race", 0.98, 0.99, ticker="KXRACE15M-A"))
    assert sorted(order(html)) == ["BTC", "GOLD", "WTI"]                                    # no Coin Race
    assert html.count('class="bd-g"') == 3 and html.count('<table class="bd-t">') == 3      # a table per group ...
    for name in ("Crypto", "Metals", "Energy"):
        assert f'<h3 class="bd-gh">{name} <span class="n">1</span></h3>' in html          # ... under its header
    assert "bd-grp" not in html                                                             # so no row names its group


def test_with_one_group_open_no_row_repeats_it():
    html = draw(market("BTC", "crypto", 0.80, 0.81), market("ETH", "crypto", 0.70, 0.71))
    assert 'class="bd-grp"' not in html


def test_the_price_column_says_it_is_the_sort():
    assert '<th scope="col" aria-sort="descending">Favorite ↓</th>' in draw(market("BTC", "crypto", 0.80, 0.81))
