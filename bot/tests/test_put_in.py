"""Put in vs profit, under the Portfolio figure: how much of your own money is in the account, and how much the bot
has made on top of it.

"Put in" is the ledger's start: your cash at the first live run, kept equal to money in minus money out by every
--rebase. "Profit" is the bot's books now (bankroll plus open bets) minus that start, so the two add up to the
Portfolio figure. A dry run or paper account says "Started with", since it's play money. With the balance hidden there
are no dollars, only the % since the start, as before.

A deposit you haven't told the bot about would read as profit, so when Kalshi holds at least $1 more (or less) than
the books, with nothing open, a note says so and how to fix it: python bot.py --rebase.

The page's fundsLine() and bookGap() are cut out of dashboard.html and run in node (skipped without node). The tests
read the text they write, and the tone (green or red) each part of it carries, not the exact markup.
    python -m pytest tests/test_put_in.py -q
"""
import json
import random
import re
import shutil
import subprocess
import types
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser

import pytest

from kalshi_bot.web import dashboard

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def function(name):
    """A top-level `function name(...) {...}` (closing at column 0), or a one-line `const name = ...`."""
    return piece(rf"^function {name}\(.*?^\}}$|^const {name} = [^\n]*$")


def run(*calls):
    """Each (function name, args) call's result, from one node process."""
    src = "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "nf", "zero", "money", "signed", "pct", "spct", "tone", "arrow")),
        function("fundsLine"), function("bookGap"),
        "const calls = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "process.stdout.write(JSON.stringify(calls.map(([f, args]) => ({ fundsLine, bookGap })[f](...args))));",
    ])
    r = subprocess.run([NODE, "-e", src], input=json.dumps(calls), capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class Reader(HTMLParser):
    """The text, each piece with the classes in force around it, and the outermost element's attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.bits, self.root = [], [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.root = self.root or attrs
        self.stack.append(set((attrs.get("class") or "").split()))

    def handle_endtag(self, tag):
        self.stack.pop()

    def handle_data(self, data):
        self.bits.append((data, set().union(*self.stack)))


def read(html):
    r = Reader()
    r.feed(html)
    r.close()
    return types.SimpleNamespace(text=re.sub(r"\s+", " ", "".join(t for t, _ in r.bits)).strip(), bits=r.bits, root=r.root or {})


def tone_of(html, words):
    """The tone (up, down, or none) in force where these words are written."""
    hits = [c & {"up", "down"} for t, c in read(html).bits if words in t]
    assert hits, f"{words!r} isn't in {html!r}"
    return hits[0]


LIVE = {"live": True, "mode": "live-prod", "start": 500.0039, "openBets": []}
DRY = {"live": False, "mode": "dry-prod", "start": 100.0, "openBets": []}


def funds(d, equity):
    return run(("fundsLine", [d, equity]))[0]


# ------------------------------------------------------------------ the line under the Portfolio figure
@needs_node
def test_a_live_account_shows_what_you_put_in_and_the_profit_on_top():
    html = funds(LIVE, 587.87)
    assert read(html).text == "Put in $500.00 · Profit ▲ +$87.87 (+17.6%)"
    assert tone_of(html, "Profit") == {"up"} and tone_of(html, "87.87") == {"up"}   # the profit is green ...
    assert tone_of(html, "Put in") == set()                                          # ... your own money isn't


@needs_node
def test_a_loss_reads_as_one():
    html = funds({**LIVE, "start": 500.0}, 487.66)
    assert read(html).text == "Put in $500.00 · Profit ▼ −$12.34 (−2.5%)"
    assert tone_of(html, "Profit") == {"down"} and tone_of(html, "Put in") == set()


@needs_node
def test_no_profit_has_no_arrow_and_no_colour():
    html = funds({**LIVE, "start": 500.0}, 500.004)
    assert read(html).text == "Put in $500.00 · Profit $0.00 (0.0%)"
    assert tone_of(html, "Profit") == set()


@needs_node
def test_a_dry_run_or_paper_account_says_started_with():
    html = funds(DRY, 105.0)
    assert read(html).text == "Started with $100.00 · Profit ▲ +$5.00 (+5.0%)"
    assert "Put in" not in html


@needs_node
@pytest.mark.parametrize("start, equity, shown", [
    (500.0039, 587.8661, "Put in $500.00 · Profit ▲ +$87.87"),    # rounded on its own, the profit would be $87.86
    (100.004, 100.006, "Put in $100.00 · Profit ▲ +$0.01"),        # ... or $0.00, under a Portfolio of $100.01
    (100.006, 100.004, "Put in $100.01 · Profit ▼ −$0.01"),
])
def test_put_in_and_profit_add_up_to_the_portfolio_figure_to_the_cent(start, equity, shown):
    assert read(funds({**LIVE, "start": start}, equity)).text.startswith(shown)


def in_cents(shown):
    return int(round(float(shown.replace(",", "")) * 100))


def cents(v):
    """money()'s figure in cents, for a value with 4 decimals whose last two aren't exactly 50 (no float tie)."""
    return int(Decimal(f"{v:.4f}").quantize(Decimal("0.01"), ROUND_HALF_UP) * 100)


@needs_node
def test_they_add_up_on_a_thousand_random_accounts():
    rng = random.Random(1011)
    pairs = []
    while len(pairs) < 1000:
        start = rng.randrange(1_0000, 20_000_0000) / 1e4
        equity = round(start * rng.uniform(0.2, 3.0), 4)
        if round(start * 1e4) % 100 != 50 and round(equity * 1e4) % 100 != 50:
            pairs.append((start, equity))
    lines = run(*(("fundsLine", [{**LIVE, "start": s}, e]) for s, e in pairs))
    shape = re.compile(r"^Put in \$([\d,]+\.\d\d) · Profit (?:[▲▼] )?([+−]?)\$([\d,]+\.\d\d) \([+−]?\d+\.\d%\)$")
    for (start, equity), html in zip(pairs, lines):
        m = shape.match(read(html).text)
        assert m, read(html).text
        put, sign, profit = m.groups()
        assert in_cents(put) == cents(start)
        assert in_cents(put) + (-1 if sign == "−" else 1) * in_cents(profit) == cents(equity), (start, equity, read(html).text)


# ------------------------------------------------------------------ the note when Kalshi and the books disagree
ACCT = {"value": 587.87, "total": 587.87, "crypto": 587.87, "held": 0}


def gap(d=LIVE, equity=587.87, acct=ACCT, hide=False, **kalshi):
    return run(("bookGap", [d, equity, acct and {**acct, **kalshi}, hide]))[0]


def check_note(html):
    """Shown as the page's other warnings are, with the command to run."""
    root = read(html).root
    assert root.get("role") == "status" and {"note", "warn"} <= set(root.get("class", "").split())
    assert re.search(r"<code[^>]*>python bot\.py --rebase</code>", html)


@needs_node
def test_a_deposit_not_yet_rebased_is_pointed_out_so_it_isnt_taken_for_profit():
    html = gap(crypto=687.87, total=687.87)
    text = read(html).text
    assert "Kalshi holds $100.00 more than the bot's books" in text
    assert "If you added money, run python bot.py --rebase so it counts as put in, not profit." in text
    check_note(html)


@needs_node
def test_a_withdrawal_not_yet_rebased_is_pointed_out_so_it_isnt_taken_for_a_loss():
    html = gap(crypto=487.87, total=487.87)
    text = read(html).text
    assert "Kalshi holds $100.00 less than the bot's books" in text
    assert "If you took money out, run python bot.py --rebase so it counts as taken out, not a loss." in text
    check_note(html)


@needs_node
def test_it_compares_the_crypto_section_and_falls_back_to_the_total():
    assert "$100.00 more" in read(gap(crypto=687.87, total=900.0)).text   # cash elsewhere has its own note
    assert "$13.00 more" in read(gap(crypto=None, total=600.87)).text


@needs_node
@pytest.mark.parametrize("cash, shown", [(101.49, False), (99.51, False), (101.5, True), (99.5, True)])
def test_a_gap_under_a_dollar_is_left_alone(cash, shown):
    html = gap(equity=100.5, crypto=cash, total=cash)
    assert bool(html) is shown and (not shown or "$1.00" in read(html).text)


@needs_node
def test_no_note_while_bets_are_open_on_either_side():
    """Mid-bet the books and Kalshi disagree for a while anyway, so only compare when nothing is riding."""
    assert gap(d={**LIVE, "openBets": [{"ticker": "KXBTC15M-X"}]}, crypto=687.87, total=687.87) == ""
    assert gap(crypto=687.87, total=687.87, held=0.005) == ""
    assert gap(crypto=687.87, total=687.87, held=0.004) != ""


@needs_node
def test_no_note_without_kalshi_or_off_a_live_account():
    assert gap(acct=None) == ""
    assert gap(d={**DRY}, crypto=687.87, total=687.87) == ""


@needs_node
def test_with_the_balance_hidden_the_note_names_no_amount():
    more, less = gap(crypto=687.87, total=687.87, hide=True), gap(crypto=487.87, total=487.87, hide=True)
    assert "Kalshi holds more than the bot's books" in read(more).text and "If you added money" in read(more).text
    assert "Kalshi holds less than the bot's books" in read(less).text and "If you took money out" in read(less).text
    assert "$" not in more and "$" not in less and "100" not in more + less


# ------------------------------------------------------------------ where render() uses them
def render_src():
    return piece(r"^function render\(\) \{.*?^\}$")


def test_the_hero_uses_the_funds_line_only_while_the_balance_shows():
    src = render_src()
    hidden = src.split("${hideBal ? `")[1].split("` : `")[0]
    assert "fundsLine" not in hidden and "spct(r)" in hidden                 # hidden: the % alone, as before
    shown_at = src.index(hidden) + len(hidden)
    call = src.find("fundsLine(d, equity)", shown_at)
    assert -1 < call < src.index("${scoreBlock(d)}")
    assert "from the bot's bets since the start" not in HTML                # the old line, which it replaces
    assert "Started with" not in src                                          # said once, by the funds line


def test_the_note_joins_the_banners_after_the_idle_cash_one():
    src = render_src()
    idle, call = src.index("outside Crypto &amp; Commodities"), src.find("bookGap(d, equity, acct, hideBal)")
    assert idle < call < src.index('patch("banners"')
