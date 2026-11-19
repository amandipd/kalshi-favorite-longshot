"""dashboard.html's positions(): the Live tab's open bets as a grid of tiles, several to a row, run for real in node.

Several positions per row, still clean. Each open bet
was a full-width row (.prow); now it's a tile (.pcard) in a responsive grid (.pgrid), and a tile keeps everything the row
had: the market's link to Kalshi (with its ↗), "settles" and the close time, the side pill with price × contracts, and
the profit if sold now with its arrow and colour ("—", muted, without a mark). The fold, its count, its "worth ... vs
cost" meta and the empty line stay as they were.

positions() and the page helpers it uses (esc, nf, zero, signed, tone, arrow, cents, hhmm, sym, title, kalshiUrl,
market, and the shared fold helper) are cut out of the page; patch() is stood in for, so a test reads the HTML it drew.
The clock's time zone is fixed (TZ=America/New_York) and the expected close times come from the page's own hhmm(), so
the tests don't depend on the machine's locale. The CSS checks read the page's <style>. The tests skip without node.

Choices these tests pin: a tile's two lines are .pc-top (the market in b.pc-m, then the profit in .pl) and .pc-bot (the
side pill, then "settles ..." in .s.muted), in that order; the grid's tiles are its direct children; the contracts in
the pill are written as today (no thousands separator); "no raw hex" also rules out rgb()/hsl() colours in the new rules.

    python -m pytest tests/test_positions_grid.py -q
"""

import json
import os
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from kalshi_bot.web import dashboard
from test_folds_live import SCRIPT, decl, fold_helper   # SCRIPT: the page's own script, as test_frontend.py cuts it

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
node_only = pytest.mark.skipif(not NODE, reason="node isn't installed")

HELPERS = ("esc", "nf", "zero", "signed", "tone", "arrow", "cents", "hhmm", "sym", "title", "kalshiUrl", "market")
HARNESS = "\n".join([
    *(decl(SCRIPT, n) for n in HELPERS),
    fold_helper(SCRIPT),
    decl(SCRIPT, "positions"),
    "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
    "const data = input.data;",
    "const out = {}, patch = (id, h) => { out[id] = h; return true; };",
    "positions();",
    "process.stdout.write(JSON.stringify({ html: out.positions, times: data.openBets.map((b) => hhmm(b.close_ts)) }));",
])
CLOSE = 1_791_831_600          # Oct 12 2026, 3:00 PM in New York
BETS = [
    {"ticker": "KXBTC15M-26OCT121500-00", "series": "KXBTC15M", "side": "yes", "price": 0.94, "contracts": 34,
     "close_ts": CLOSE, "cost": 32.2, "fee": 0.13, "unrealized": 1.25},
    {"ticker": "KXETH15M-26OCT121500-00", "series": "KXETH15M", "side": "no", "price": 0.965, "contracts": 7,
     "close_ts": CLOSE, "cost": 6.76, "fee": 0.02, "unrealized": -0.4},
    {"ticker": "KXGOLD15M-26OCT121515-15", "series": "KXGOLD15M", "side": "yes", "price": 0.91, "contracts": 12,
     "close_ts": CLOSE + 900, "cost": 10.92, "fee": 0.07, "unrealized": None},
]
EMPTY_LINE = '<p class="empty-line"><b>No open bets</b> <span>New ones are placed at minute 8 of each 15-minute window.</span></p>'


def test_the_harness_finds_every_helper():
    for n in HELPERS + ("positions",):
        assert decl(SCRIPT, n), f"dashboard.html no longer has {n}"


def draw(bets, unrealized=0.85):
    r = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"data": {"openBets": bets, "unrealized": unrealized}}),
                       capture_output=True, text=True, encoding="utf-8", timeout=30,
                       env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ------------------------------------------------------------------ a small DOM, to read the tiles back


class El:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    @property
    def cls(self):
        return (self.attrs.get("class") or "").split()

    @property
    def els(self):
        return [k for k in self.kids if isinstance(k, El)]

    def text(self):
        return "".join(k if isinstance(k, str) else k.text() for k in self.kids)

    def words(self):
        """Every text node's words, element by element (so two elements' texts never run together)."""
        return [w for k in self.kids for w in (k.split() if isinstance(k, str) else k.words())]

    def find(self, cls):
        out = [self] if cls in self.cls else []
        for k in self.els:
            out += k.find(cls)
        return out


class Tree(HTMLParser):
    VOID = {"br", "img", "input", "meta", "link", "hr", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.at = El("root", {})
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        el = El(tag, attrs, self.at)
        self.at.kids.append(el)
        if tag not in self.VOID:
            self.at = el

    def handle_endtag(self, tag):
        node = self.at
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.at = node.parent

    def handle_data(self, data):
        self.at.kids.append(data)


def tiles(html):
    [grid] = Tree(html).root.find("pgrid")
    return grid, grid.els


# ------------------------------------------------------------------ the tiles


@node_only
def test_one_grid_with_a_tile_per_open_bet_in_order():
    grid, cards = tiles(draw(BETS)["html"])
    assert grid.attrs.get("role") == "list"
    assert len(cards) == 3 and all("pcard" in c.cls and c.attrs.get("role") == "listitem" for c in cards)
    assert [c.find("pc-m")[0].text().strip() for c in cards] == ["BTC 15 min ↗", "ETH 15 min ↗", "GOLD 15 min ↗"]


@node_only
def test_each_tile_links_its_market_on_kalshi():
    _, cards = tiles(draw(BETS)["html"])
    for card, bet in zip(cards, BETS):
        [m] = card.find("pc-m")
        assert m.tag == "b"
        [a] = [e for e in m.els if e.tag == "a"]
        series, slug = bet["ticker"].split("-")[0].lower(), "-".join(bet["ticker"].split("-")[:2]).lower()
        assert a.attrs["href"] == f"https://kalshi.com/markets/{series}/{series}/{slug}"
        assert a.attrs["target"] == "_blank" and a.attrs["rel"] == "noopener"
        assert a.attrs["title"] == f"{bet['ticker']} on Kalshi"
        assert [e.text() for e in a.find("ext")] == [" ↗"]


@node_only
def test_each_tile_has_the_side_pill_and_when_it_settles():
    out = draw(BETS)
    _, cards = tiles(out["html"])
    pills = [("pill yes", "YES 94¢ × 34"), ("pill no", "NO 96.5¢ × 7"), ("pill yes", "YES 91¢ × 12")]
    for card, (cls, text), when in zip(cards, pills, out["times"]):
        [bot] = card.find("pc-bot")
        pill, settles = bot.els
        assert " ".join(pill.cls) == cls and pill.text() == text
        assert {"s", "muted"} <= set(settles.cls) and settles.text() == f"settles {when}"
    assert re.fullmatch(r"3:00\sPM|15:00", out["times"][0])                 # the page's own clock, New York time


@node_only
def test_each_tile_has_its_profit_with_arrow_and_colour_or_a_muted_dash():
    _, cards = tiles(draw(BETS)["html"])
    want = [({"pl", "up"}, "▲ +$1.25"), ({"pl", "down"}, "▼ −$0.40"), ({"pl", "muted"}, "—")]
    for card, (cls, text) in zip(cards, want):
        [top] = card.find("pc-top")
        name, pl = top.els
        assert "pc-m" in name.cls
        assert set(pl.cls) == cls and pl.text() == text


@node_only
def test_a_tile_is_two_lines_top_and_bottom():
    _, cards = tiles(draw(BETS)["html"])
    for card in cards:
        assert [e.cls[0] for e in card.els] == ["pc-top", "pc-bot"]


@node_only
def test_no_rows_are_left():
    html = draw(BETS)["html"]
    assert "prow" not in html and 'class="pm"' not in html


@node_only
def test_every_word_and_number_a_row_had_is_in_its_tile():
    """The row's text, word for word, from the same bets: every token is still drawn."""
    out = draw(BETS)
    words = Tree(out["html"]).root.words()
    for bet, when in zip(BETS, out["times"]):
        for token in ("settles", *when.split()):
            assert token in words
    for token in ("BTC", "ETH", "GOLD", "15", "min", "↗", "YES", "NO", "94¢", "96.5¢", "91¢", "×", "34", "7", "12",
                  "▲", "+$1.25", "▼", "−$0.40", "—"):
        assert token in words, token


# ------------------------------------------------------------------ what stays as it was


@node_only
def test_the_fold_its_count_and_meta_are_unchanged():
    html = draw(BETS)["html"]
    assert 'data-fold-key="live.positions"' in html
    assert 'Positions <span class="n">3</span>' in html
    assert '<span class="fold-m">worth +$0.85 vs cost</span>' in html


@node_only
def test_no_open_bets_keeps_the_empty_line_and_no_meta():
    html = draw([], unrealized=0)["html"]
    assert EMPTY_LINE in html
    assert 'Positions <span class="n">0</span>' in html
    assert "fold-m" not in html and "vs cost" not in html
    assert "pgrid" not in html and "pcard" not in html


# ------------------------------------------------------------------ the CSS


def css():
    style = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)
    return re.sub(r"/\*.*?\*/", "", style, flags=re.S)


def blocks(text, media=None):
    """(selector, body, media) for every rule, the ones inside @media blocks with that block's condition."""
    out, i = [], 0
    while True:
        j = text.find("{", i)
        if j < 0:
            return out
        head = text[i:j].strip()
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            k += 1
        body = text[j + 1:k - 1]
        if head.startswith("@media"):
            out += blocks(body, head)
        else:
            out.append((head, body, media))
        i = k


RULES = blocks(css())
PHONE = "@media (max-width: 560px)"


def rule(selector, media=None):
    """The declarations of every rule naming exactly `selector` (alone or in a selector list), at the top level or in
    that @media block."""
    found = [b for s, b, m in RULES if selector in [x.strip() for x in s.split(",")] and m == media]
    assert found, f"no {selector} rule{' in ' + media if media else ''}"
    return " ".join(" ".join(b.split()) for b in found)


def test_the_grid_fills_rows_with_as_many_tiles_as_fit():
    g = rule(".pgrid")
    assert "display: grid" in g
    assert "grid-template-columns: repeat(auto-fill, minmax(" in g


def test_phones_get_two_tiles_a_row():
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in rule(".pgrid", PHONE)


def test_tiles_are_parted_by_hairlines_clipped_at_the_panels_edge():
    assert "overflow: hidden" in rule(".pgrid")
    shadow = re.search(r"box-shadow:\s*([^;]+)", rule(".pcard"))
    assert shadow and shadow.group(1).count("var(--line)") == 2
    assert "border:" not in rule(".pcard")                        # hairlines, not a box around each tile


def test_a_tile_lights_on_hover_and_long_text_wraps_inside_it():
    assert "background: var(--hover)" in rule(".pcard:hover")
    assert "min-width: 0" in rule(".pcard")
    for s in (".pc-top", ".pc-bot"):
        assert "flex-wrap: wrap" in rule(s)


def test_the_row_rules_are_gone():
    assert ".prow" not in HTML


def test_the_new_rules_use_the_pages_tokens_only():
    new = [(s, b) for s, b, _ in RULES if re.search(r"\.(pgrid|pcard|pc-)", s)]
    assert len(new) >= 5
    for s, b in new:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", b), s
