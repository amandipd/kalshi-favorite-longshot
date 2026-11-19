"""The Live tab's market board says "In range" only before the bot's entry at minute 8 of each window.

From minute 8 on, the bot has already made its one entry in that window, so a price in its buying range no longer
means anything is about to be bought: the label and the row's edge go until the next window starts. The entry minute is
the server's (state()["limits"]["minute"], bot.MINUTE), with the page's own LIMITS.minute when the state hasn't come
yet. boardBlock() is cut out of the page with the helpers it uses (with the shared fold helper it draws through once
the Live tab folds) and run in node (skipped without node).
"""

import json
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_folds_live import fold_helper

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node isn't installed")

WINDOW = 1_791_599_400          # a window's start: a multiple of 900 s
IN_RANGE = '<span class="bd-in"'


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def harness():
    return "\n".join([
        piece(r"^const esc = .*?;$"), piece(r"^const zero = .*?;$"), piece(r"^const tone = .*?;$"), piece(r"^const cents = .*?;$"),
        piece(r"^const kalshiUrl = .*?^\};$"),   # each market's name links to it on Kalshi
        piece(r"^const BOARD_FRESH = .*?;"), piece(r"^const BOARD_GROUPS = .*?;"), piece(r"^const lastFav = .*?;"),
        piece(r"^function flashOf\(m\) \{.*?^\}$"), piece(r"^function sparkOf\(m\) \{.*?^\}$"), piece(r"^function boardBlock\(\) \{.*?^\}$"),
        fold_helper(HTML),   # the board draws inside a fold once the Live tab folds (empty before that)
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "const nowS = () => input.now, LIMITS = { lo: 0.9, hi: 0.999, minute: 8 }, data = input.data;",
        "let board = input.board, boardErr = false;",
        "const out = {}, patch = (id, h) => { out[id] = h; return true; };",
        "boardBlock();",
        "process.stdout.write(Object.values(out).join(''));",
    ])


def market(label="BTC", ask=0.95, bid=None):
    bid = round(ask - 0.01, 4) if bid is None else bid
    return {"ticker": f"KX{label}15M-A", "label": label, "group": "crypto", "yes_bid": bid, "yes_ask": ask,
            "favSide": "yes", "favPrice": ask, "path": []}


def draw(secs_into_window, *markets, data="default"):
    data = {"groups": ["crypto"], "limits": {"minute": 8}} if data == "default" else data
    live = {"heartbeat": "2026-10-10T09:00:00Z", "source": "stream", "band": [0.9, 0.999], "markets": list(markets or [market()])}
    r = subprocess.run([NODE, "-e", harness()], input=json.dumps({"now": WINDOW + secs_into_window, "data": data, "board": {"live": live}}),
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def shows_in_range(html):
    return IN_RANGE in html or 'class="bd-r in' in html


@pytest.mark.parametrize("secs", [0, 60, 300, 479])
def test_before_minute_8_a_price_in_range_says_so(secs):
    html = draw(secs)
    assert IN_RANGE in html and 'class="bd-r in"' in html


@pytest.mark.parametrize("secs", [480, 481, 525, 600, 840, 899])
def test_from_minute_8_on_it_no_longer_says_in_range(secs):
    assert not shows_in_range(draw(secs))


def test_the_next_window_says_in_range_again():
    assert not shows_in_range(draw(899))
    assert IN_RANGE in draw(900)                         # second 0 of the next window


def test_after_minute_8_the_rest_of_the_row_is_unchanged():
    html = draw(600)
    assert 'class="bd-mk" href="https://kalshi.com/markets/kxbtc15m/kxbtc15m/kxbtc15m-a"' in html   # its name, a link to it on Kalshi
    assert '<span class="pill yes">YES</span><span class="bd-px">95¢' in html
    assert re.search(r'<tr class="bd-r">', html)


def test_a_price_out_of_range_never_says_in_range():
    assert not shows_in_range(draw(100, market(ask=0.80)))


def test_the_entry_minute_comes_from_the_server():
    data = {"groups": ["crypto"], "limits": {"minute": 5}}
    assert IN_RANGE in draw(299, data=data)
    assert not shows_in_range(draw(300, data=data))


def test_before_the_state_arrives_it_uses_the_pages_own_entry_minute():
    assert IN_RANGE in draw(479, data=None)
    assert not shows_in_range(draw(480, data=None))
    assert not shows_in_range(draw(480, data={"groups": ["crypto"]}))   # a state with no limits yet


def test_the_label_still_names_the_buying_range():
    assert '<span class="bd-in" title="In the bot\'s 90¢–99.9¢ buying range">In range</span>' in draw(100)
