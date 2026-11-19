"""The live bot's lowest price, raised from 90c to 92c on Oct 14, 2026.

Why: live, Sep 28 - Oct 14, the 90-92c band lost 31 of 217 bets against about 16 expected at the backtest's rate (about
a 1 in 1,700 chance) and made -$163, while every dearer band made money (research/kalshi_15min/live_losses.py).

Terms: the floor is LO, the lowest ask at which the bot buys a favourite; HI (99.9c) is the highest. A favourite is
bought when LO <= its ask <= HI, so 92.0c exactly is bought and 91.9c is skipped.

What must hold: LO is 0.92 and HI 0.999; a minute-8 favourite outside them is skipped with a reason written from LO and
HI ("favorite at 91.9c is outside 92-99.9c"), whatever they're set to, and one inside is bought; fast entry on paper
buys nothing at a mark ask under 92c and can buy at 92c; the dashboard's server sends the new floor (state()'s limits
and the live board's band) and the page's fallback LIMITS carries it; the floor's line in bot.py says when and why it
rose. No docstring in bot.py, and neither of README.md's two statements of the live rule (its opening paragraph and
"What it buys"), still gives the band as 90-99.9c: a note on the change says "from 90c", not the old band in full.
The research's own text (its backtests bought from 90c) and the price-floor panel's 90c row are left alone.
Nothing here touches the network or an account.

    python -m pytest tests/test_floor_92.py -q
"""
import ast
import inspect
import os
import re

import pytest

from kalshi_bot import bot
from layout import BOT
from kalshi_bot.web import dashboard
from test_bot import ENTRY, THREE_DOLLAR_START, W, FakeKalshi, decisions, run, start_ledger
from test_dashboard_more import Exchange, home, mode_db, quiet  # noqa: F401 (home is a fixture)
from test_fast_shadow import IGNORED, at_mark, paper_bot, raw, row
from test_flow import GOLD, NO98, YES96, bets, mk, slept  # noqa: F401 (slept: no sleeps)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


BTC = "KXBTC15M-A"                     # FakeKalshi's BTC market in the window W
README = os.path.join(BOT, "README.md")
SOURCE = open(bot.__file__, encoding="utf-8").read()

# The live band written out: "90-99.9c", "90–99.9¢", "90¢ to 99.9¢", "90¢–99.9¢" (and the same from 92)
OLD = re.compile(r"(?<![\d.])90\s*[c¢]?\s*(?:-|–|to)\s*99\.9\s*[c¢]")
NEW = re.compile(r"(?<![\d.])92\s*[c¢]?\s*(?:-|–|to)\s*99\.9\s*[c¢]")


def yes_at(ask):
    """A book (as GET /markets/{t}/orderbook answers it) whose favourite is YES at `ask`, its bid 1c under."""
    return {"yes_dollars": [[f"{ask - 0.01:.4f}", "100"]], "no_dollars": [[f"{1 - ask:.4f}", "50"]]}


def no_at(price):
    """A book whose favourite is NO at `price`: the YES bid is 1 - price, the YES ask 1c over it."""
    return {"yes_dollars": [[f"{1 - price:.4f}", "80"]], "no_dollars": [[f"{price - 0.01:.4f}", "40"]]}


def btc_only(book):
    """FakeKalshi with one market in the window, BTC, on this book (no GOLD or ETH to muddy the orders)."""
    fake = FakeKalshi()
    fake.books = {"KXBTC15M": book}
    return fake


# ------------------------------------------------------------------ the rule
def test_the_floor_is_92c_and_the_top_still_99_9c():
    assert (bot.LO, bot.HI) == (0.92, 0.999)


@pytest.mark.parametrize("book, reason", [
    (yes_at(0.919), "favorite at 91.9c is outside 92-99.9c"),   # a tenth of a cent under the floor
    (yes_at(0.91), "favorite at 91.0c is outside 92-99.9c"),
    (yes_at(0.90), "favorite at 90.0c is outside 92-99.9c"),    # the old floor
    (no_at(0.919), "favorite at 91.9c is outside 92-99.9c"),    # a NO favourite, the same
])
def test_a_minute_8_favourite_under_92c_is_skipped_live(env, book, reason):
    fake = btc_only(book)
    run(env, fake, live=True)
    assert decisions(env) == {BTC: ("skip", reason)}
    assert fake.orders == [] and BTC not in bets(env)


@pytest.mark.parametrize("book, side, ask", [
    (yes_at(0.92), "yes", 0.92),     # exactly the floor: in
    (no_at(0.92), "no", 0.92),
    (yes_at(0.999), "yes", 0.999),   # exactly the top: in
    (no_at(0.999), "no", 0.999),
])
def test_a_minute_8_favourite_from_92c_to_99_9c_is_bought_live(env, book, side, ask):
    fake = btc_only(book)
    run(env, fake, live=True)
    limit = bot.limit_for(ask)
    [order] = fake.orders
    assert decisions(env)[BTC][0] == "bet"
    assert order["ticker"] == BTC and order["time_in_force"] == "immediate_or_cancel"
    assert (order["side"], order["price"]) == (("bid", f"{limit:.4f}") if side == "yes" else ("ask", f"{1 - limit:.4f}"))
    assert order["count"] == "3" and bets(env)[BTC]["side"] == side      # $3 (1.5% of $200) buys 3 contracts


def test_a_favourite_over_99_9c_is_still_skipped(env):
    fake = btc_only(yes_at(0.9995))
    run(env, fake, live=True)
    action, reason = decisions(env)[BTC]
    assert action == "skip" and reason.startswith("favorite at ") and reason.endswith("c is outside 92-99.9c")
    assert fake.orders == []


@pytest.mark.parametrize("lo, hi, ask, reason", [
    (0.95, 0.999, 0.94, "favorite at 94.0c is outside 95-99.9c"),
    (0.95, 0.98, 0.985, "favorite at 98.5c is outside 95-98c"),
    (0.925, 0.995, 0.92, "favorite at 92.0c is outside 92.5-99.5c"),
])
def test_the_skip_reason_is_written_from_lo_and_hi(env, monkeypatch, lo, hi, ask, reason):
    """Never hard-coded: set LO and HI to anything and the reason says them."""
    monkeypatch.setattr(bot, "LO", lo)
    monkeypatch.setattr(bot, "HI", hi)
    fake = btc_only(yes_at(ask))
    run(env, fake, live=True)
    assert decisions(env) == {BTC: ("skip", reason)} and fake.orders == []


def test_with_lo_moved_a_favourite_inside_it_is_still_bought(env, monkeypatch):
    monkeypatch.setattr(bot, "LO", 0.95)
    fake = btc_only(yes_at(0.95))
    run(env, fake, live=True)
    assert decisions(env)[BTC][0] == "bet" and len(fake.orders) == 1


# ------------------------------------------------------------------ fast entry, on paper
@pytest.mark.parametrize("side, answer, seen", [
    ("yes", raw(no=[(0.09, 5)]), 0.91),       # YES at 91c at the mark: inside the old band, under the new floor
    ("no", raw(yes=[(0.09, 5)]), 0.91),
    ("yes", raw(no=[(0.081, 5)]), 0.919),     # 91.9c
])
def test_fast_entry_buys_nothing_at_a_mark_ask_under_92c(env, side, answer, seen):
    t, m, top = (BTC, mk(BTC, YES96), 0.96) if side == "yes" else (GOLD, mk(GOLD, NO98), 0.98)
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, top, 3, IGNORED)])
    r = row(env, t)
    assert (r["seen"], r["limit_price"], r["status"]) == (seen, None, "open")
    assert (r["extra"], r["cost"], r["fee"]) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("side, answer", [
    ("yes", raw(no=[(0.08, 5)])),             # YES at 92c at the mark: the floor itself
    ("no", raw(yes=[(0.08, 5)])),
])
def test_fast_entry_can_buy_at_a_mark_ask_of_92c(env, side, answer):
    t, m, top = (BTC, mk(BTC, YES96), 0.96) if side == "yes" else (GOLD, mk(GOLD, NO98), 0.98)
    b = paper_bot(env, {t: at_mark(answer)})
    b.fast_shadow(ENTRY, W, [(m, side, top, 3, IGNORED)])
    r = row(env, t)
    assert (r["seen"], r["limit_price"], r["extra"], r["status"]) == (0.92, bot.limit_for(0.92), 3, "open")
    assert r["cost"] == pytest.approx(3 * 0.92)


# ------------------------------------------------------------------ the dashboard's server and page
def test_the_dashboard_state_sends_the_new_floor(home):
    mode_db(home, "live-prod")
    lim = dashboard.state("live-prod")["limits"]
    assert (lim["lo"], lim["hi"]) == (0.92, 0.999)


def test_the_live_boards_band_is_92c_to_99_9c():
    f = quiet(Exchange())
    f.step(W + 125)
    assert f.snapshot(W + 126)["band"] == [0.92, 0.999]


def test_the_pages_fallback_limits_carry_the_new_floor():
    """dashboard.html's LIMITS, used until the server answers: lo 0.92, hi 0.999."""
    html = open(dashboard.PAGE, encoding="utf-8").read()
    limits = re.search(r"const LIMITS = \{(.*?)\};", html, re.S).group(1)
    lo, hi = (float(re.search(rf"\b{k}: ([\d.]+)", limits).group(1)) for k in ("lo", "hi"))
    assert (lo, hi) == (0.92, 0.999)


# ------------------------------------------------------------------ bot.py's text
def docstrings():
    """(name, docstring) for the module and every class and function in bot.py."""
    nodes = ast.walk(ast.parse(SOURCE))
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return [(getattr(n, "name", "bot.py"), ast.get_docstring(n)) for n in nodes if isinstance(n, kinds) and ast.get_docstring(n)]


def test_no_docstring_in_bot_py_gives_the_old_band():
    docs = docstrings()
    assert docs, "found no docstrings: the walk needs updating"
    assert [name for name, d in docs if OLD.search(d)] == []


@pytest.mark.parametrize("where", ["module", "fast_shadow"])
def test_the_module_and_fast_shadow_docstrings_give_the_new_band(where):
    """Line 3 ("buys each ... favourite") and fast_shadow's "an ask outside ...": 92-99.9c, or LO and HI by name."""
    doc = bot.__doc__ if where == "module" else bot.Bot.fast_shadow.__doc__
    assert NEW.search(doc) or (re.search(r"\bLO\b", doc) and re.search(r"\bHI\b", doc)), doc


def test_the_skip_reason_has_no_band_written_into_it():
    src = inspect.getsource(bot.Bot.decide_window)
    assert "is outside" in src and not OLD.search(src)


def test_the_floors_line_says_when_and_why_it_rose():
    """The comment on `LO, HI = ...` (on its line, or comment lines right above or below it): raised on Oct 14, with
    the research that showed why (research/kalshi_15min/live_losses.py)."""
    lines = SOURCE.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("LO, HI ="))
    a, b = i, i + 1
    while a > 0 and lines[a - 1].lstrip().startswith("#"):
        a -= 1
    while b < len(lines) and lines[b].lstrip().startswith("#"):
        b += 1
    note = "\n".join(lines[a:b])
    assert re.search(r"Oct(?:ober)? 14", note) and "live_losses.py" in note, note


# ------------------------------------------------------------------ README.md's live rule
def readme_rule():
    """README.md's two statements of the live rule: its opening (everything before the first ## heading) and the
    "What it buys" section. Nothing past them: the dashboard and research notes describe the backtests."""
    text = open(README, encoding="utf-8").read()
    intro = text.split("\n## ", 1)[0]
    buys = re.search(r"^## What it buys\n(.*?)(?=^## )", text, re.S | re.M)
    assert buys, "README.md has no '## What it buys' section"
    return intro, buys.group(1)


def test_the_readme_gives_the_live_band_as_92c_to_99_9c():
    intro, buys = readme_rule()
    assert not OLD.search(intro) and not OLD.search(buys)
    assert NEW.search(intro), intro
    price = next((line for line in buys.splitlines() if line.startswith("| Price |")), "")
    assert NEW.search(price), price


def test_the_readme_says_when_the_floor_rose():
    intro, buys = readme_rule()
    assert re.search(r"Oct(?:ober)? 14", intro + buys)
