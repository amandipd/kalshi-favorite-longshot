"""How much money was staked, on the Live tab.

How much money was staked. state() now sends "staked": over every bet in the
ledger, open and settled, what the contracts cost ("all": price x contracts, fees aside, as "fees" is already sent on
its own) and how many bets ("bets"); when the first one was placed ("since"); the cost of the bets placed in the last 24
hours ("day", the bets dayBets counts: placed_ts >= now - 24 h); and over the settled bets, their cost ("settled") and
their P&L ("profit"). Money is rounded to the cent. An empty ledger sends 0.0s, 0 bets and since None.

The hero shows it as a line of its own, right under the funds line ("Put in ... · Profit ...") and before the
"Live from Kalshi ..." / "From the bot's books" line, in the classes the hero already uses (fmeta, muted):

    Staked $13,316.40 in 1,234 bets since Sep 18 · $412.50 in the last 24 hours · profit 2.3¢ per $1 staked

"bet" for one; the date is since's local date as the Orders fold writes it; the ¢ figure is profit / settled x 100 to
1 decimal, with the page's minus (U+2212) for a loss and no "+" for a gain, and it goes (with its " · ") while nothing
has settled. No line with the balance hidden (the hidden view is unchanged), from a server that sends no staked, or
with no bets. Nothing else in the hero changes.

The page is test_folds_live.py's stand-in browser: dashboard.html's whole script loaded in node, drawn from that file's
fixed Live tab data (folds_baseline_live.json) with a staked figure added; the clock and time zone are fixed. The node
tests skip themselves without node.

    python -m pytest tests/test_staked.py -q
"""

import json
import re

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, add_bet, home, mode_db  # noqa: F401  (home is a fixture)
from test_folds_live import HTML, El, golden, missing, needs_node, run

DAY = 86400
KEYS = {"all", "bets", "since", "day", "settled", "profit"}


def staked(mode="live-prod"):
    s = dashboard.state(mode)
    assert "staked" in s, "state() sends no staked"
    return s, s["staked"]


# ------------------------------------------------------------------ the server
def test_staked_sums_every_bet_the_last_day_and_the_settled_ones(home):
    db = mode_db(home, "live-prod", start=500.0)
    add_bet(db, "KXBTC15M-B", price=0.92, contracts=3, status="lost", fee=0.02, placed=NOW - DAY - 60)  # over a day ago
    add_bet(db, "KXBTC15M-A", price=0.94, contracts=5, status="won", fee=0.01, placed=NOW - 3 * DAY)    # the first, written second
    add_bet(db, "KXETH15M-C", price=0.95, contracts=4, status="won", fee=0.01, placed=NOW - 4 * 3600)
    add_bet(db, "KXSOL15M-D", price=0.91, contracts=6, status="lost", fee=0.03, placed=NOW - 2 * 3600)
    add_bet(db, "KXXRP15M-E", price=0.96, contracts=7, status="open", fee=0.02, placed=NOW - 600)       # still open
    s, st = staked()
    assert set(st) == KEYS
    assert st == {"all": 23.44,                  # 4.70 + 2.76 + 3.80 + 5.46 + 6.72: open and settled, no fees
                  "bets": 5,
                  "since": NOW - 3 * DAY,        # the first placed, not the first written
                  "day": 15.98,                  # 3.80 + 5.46 + 6.72: not the bet placed a day and a minute ago
                  "settled": 16.72,              # 4.70 + 2.76 + 3.80 + 5.46
                  "profit": -7.79}               # 0.29 - 2.78 + 0.19 - 5.49: each settled bet's pnl, fees in
    assert s["dayBets"] == 3                     # the same bets the day's count counts
    assert st["all"] != round(st["all"] + s["fees"], 2)                                                   # fees aside
    json.dumps(st)                               # the API sends it as JSON


@pytest.mark.parametrize("ago, counted", [(DAY, True), (DAY + 1, False), (DAY - 1, True)],
                         ids=["exactly 24 h ago", "a second more", "a second less"])
def test_the_day_is_the_bets_placed_in_the_last_24_hours_as_day_bets_counts(home, ago, counted):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-EDGE", price=0.93, contracts=4, status="won", placed=NOW - ago)
    add_bet(db, "KXETH15M-NEW", price=0.95, contracts=2, status="open", placed=NOW - 60)
    s, st = staked()
    assert st["day"] == (5.62 if counted else 1.9)
    assert s["dayBets"] == (2 if counted else 1)
    assert st["all"] == 5.62 and st["bets"] == 2 and st["since"] == NOW - ago


def test_money_is_rounded_to_the_cent(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-A", price=0.9567, contracts=7, status="won", pnl=0.12344, placed=NOW - 2 * DAY)  # costs 6.6969
    add_bet(db, "KXETH15M-B", price=0.9133, contracts=3, status="open", placed=NOW - 300)                 # costs 2.7399
    _, st = staked()
    assert st == {"all": 9.44, "bets": 2, "since": NOW - 2 * DAY, "day": 2.74, "settled": 6.7, "profit": 0.12}


def test_float_noise_is_rounded_away(home):
    db = mode_db(home, "live-prod")
    for i, (price, n, pnl) in enumerate([(0.95, 3, 0.1), (0.92, 3, 0.2)]):
        add_bet(db, f"KXBTC15M-{i}", price=price, contracts=n, status="won", pnl=pnl, placed=NOW - 3600 * (i + 1))
    assert 0.95 * 3 + 0.92 * 3 != 5.61 and 0.1 + 0.2 != 0.3                                              # the raw sums aren't
    _, st = staked()
    assert st["all"] == st["day"] == st["settled"] == 5.61 and st["profit"] == 0.3


def test_with_only_open_bets_nothing_has_settled(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-A", price=0.95, contracts=10, status="open", placed=NOW - 900)
    add_bet(db, "KXETH15M-A", price=0.92, contracts=5, status="open", placed=NOW - 120)
    _, st = staked()
    assert st == {"all": 14.1, "bets": 2, "since": NOW - 900, "day": 14.1, "settled": 0.0, "profit": 0.0}


def test_an_empty_ledger_stakes_nothing(home):
    mode_db(home, "live-prod")
    _, st = staked()
    assert st == {"all": 0.0, "bets": 0, "since": None, "day": 0.0, "settled": 0.0, "profit": 0.0}
    assert st["since"] is None and st["bets"] == 0
    json.dumps(st)


# ------------------------------------------------------------------ the page: the hero, in the stand-in browser
SINCE = NOW - 10 * DAY                           # Sep 18, 3 PM ET
STAKED = {"all": 13316.4, "bets": 1234, "since": SINCE, "day": 412.5, "settled": 12900.0, "profit": 296.7}
LINE = "Staked $13,316.40 in 1,234 bets since Sep 18 · $412.50 in the last 24 hours · profit 2.3¢ per $1 staked"
HIDDEN = {"hideBal": "1"}
CSS = set(re.findall(r"\.([A-Za-z][\w-]*)", HTML.split("<style>", 1)[1].split("</style>", 1)[0])) if "<style>" in HTML else set()


def inputs(**state):
    """The fixed Live tab data with these state keys changed; a key set to ... is left out."""
    g = golden()
    st = {k: v for k, v in {**g["state"], **state}.items() if v is not ...}
    return {**g, "state": st}


def page(store=None, **state):
    return run(store=store, inputs=inputs(**state))[0]


def read(el):
    """What an element reads as, as the browser's textContent: its text run together, whitespace collapsed."""
    return " ".join("".join(el.texts()).split())


def outline(el):
    """An element's tag, attributes and contents, for comparing two drawings of it."""
    return (el.tag, tuple(sorted(el.attrs.items())),
            tuple(outline(k) if isinstance(k, El) else " ".join(k.split()) for k in el.kids if isinstance(k, El) or k.strip()))


def hero(p):
    return p.by_id("hero")


def line_of(p):
    """The hero's staked line, after checking it sits right after the funds line and right before the meta line."""
    kids = hero(p).children()
    hits = [i for i, k in enumerate(kids) if read(k).startswith("Staked")]
    assert len(hits) == 1, f"expected one 'Staked ...' line in the hero, found {len(hits)}: {[read(k) for k in kids]}"
    i = hits[0]
    el = kids[i]
    assert el.tag == "div" and set(el.attrs.get("class", "").split()) == {"fmeta", "muted"}, \
        f'the staked line is <{el.tag} class="{el.attrs.get("class")}">, not <div class="fmeta muted">'
    before, after = kids[i - 1], kids[i + 1] if i + 1 < len(kids) else None
    assert before.attrs.get("class") == "fd" and read(before).startswith(("Put in", "Started with")), \
        f"the staked line doesn't follow the funds line: it follows {read(before)!r}"
    assert after is not None and read(after).startswith(("Live from Kalshi", "From the bot's books")), \
        f"the staked line isn't followed by the Kalshi / bot's books line: {after and read(after)!r}"
    for e in el.els():
        for c in e.attrs.get("class", "").split():
            assert c in CSS, f"the staked line uses a class the page doesn't have: {c}"
    return read(el)


def no_line(p):
    text = read(hero(p))
    assert "staked" not in text.lower(), f"the hero shows a staked line: {text!r}"


@needs_node
def test_the_line_reads_as_the_spec_writes_it():
    assert line_of(page(staked=STAKED)) == LINE


@needs_node
def test_it_sits_under_the_funds_line_and_before_from_the_bots_books():
    p = page(staked=STAKED, kalshi=None)                 # no Kalshi account: the meta line is the bot's books
    assert line_of(p) == LINE


@needs_node
def test_nothing_else_in_the_hero_changes():
    with_it, without = hero(page(staked=STAKED)).children(), hero(page()).children()
    rest = [k for k in with_it if not read(k).startswith("Staked")]
    assert [outline(k) for k in rest] == [outline(k) for k in without]


@needs_node
def test_one_bet_is_a_bet():
    line = line_of(page(staked={"all": 9.5, "bets": 1, "since": SINCE, "day": 9.5, "settled": 9.5, "profit": 0.4}))
    assert line == "Staked $9.50 in 1 bet since Sep 18 · $9.50 in the last 24 hours · profit 4.2¢ per $1 staked"


@needs_node
def test_two_bets_are_bets():
    line = line_of(page(staked={"all": 19.0, "bets": 2, "since": SINCE, "day": 9.5, "settled": 9.5, "profit": 0.4}))
    assert line.startswith("Staked $19.00 in 2 bets since Sep 18 · ")


@needs_node
def test_a_loss_per_dollar_has_the_pages_minus():
    line = line_of(page(staked={**STAKED, "profit": -150.0}))   # -150 / 12,900 = -1.16¢ per $1
    assert line == "Staked $13,316.40 in 1,234 bets since Sep 18 · $412.50 in the last 24 hours · profit −1.2¢ per $1 staked"
    assert "-" not in line


@needs_node
def test_a_gain_per_dollar_has_no_plus():
    line = line_of(page(staked={**STAKED, "settled": 1000.0, "profit": 123.4}))   # 12.34¢ per $1
    assert line.endswith(" · profit 12.3¢ per $1 staked") and "+" not in line


@needs_node
@pytest.mark.parametrize("profit", [0.0, -0.004], ids=["nothing made", "rounds to nothing"])
def test_a_figure_that_shows_as_nothing_has_no_sign(profit):
    # the page's own rule (zero(): what rounds to nothing gets no sign); "0.0" rather than "−0.0"
    line = line_of(page(staked={**STAKED, "settled": 100.0, "profit": profit}))
    assert line.endswith(" · profit 0.0¢ per $1 staked"), line


@needs_node
def test_nothing_settled_no_cents_figure():
    line = line_of(page(staked={"all": 9.5, "bets": 1, "since": SINCE, "day": 9.5, "settled": 0.0, "profit": 0.0}))
    assert line == "Staked $9.50 in 1 bet since Sep 18 · $9.50 in the last 24 hours"
    for bad in ("profit", "¢", "NaN", "Infinity", "undefined"):
        assert bad not in line


@needs_node
def test_the_last_24_hours_shows_even_at_nothing():
    line = line_of(page(staked={**STAKED, "day": 0.0}))
    assert " · $0.00 in the last 24 hours · " in line


@needs_node
def test_the_date_is_the_first_bets_day_where_the_page_is():
    late = NOW - 10 * DAY + 7 * 3600                     # Sep 18, 10 PM ET: Sep 19 in UTC
    assert " since Sep 18 · " in line_of(page(staked={**STAKED, "since": late}))


@needs_node
def test_money_and_counts_get_their_separators():
    line = line_of(page(staked={**STAKED, "all": 1234567.891, "bets": 1234, "day": 98765.4}))
    assert line.startswith("Staked $1,234,567.89 in 1,234 bets since Sep 18 · $98,765.40 in the last 24 hours · ")


@needs_node
def test_with_the_balance_hidden_there_is_no_line_and_the_hidden_view_is_unchanged():
    p = page(store=HIDDEN, staked=STAKED)
    no_line(p)
    assert outline(hero(p)) == outline(hero(page(store=HIDDEN)))
    assert "13,316" not in p.markup and "412.50" not in p.markup


@needs_node
@pytest.mark.parametrize("value", [..., None], ids=["no staked", "staked null"])
def test_an_old_server_without_staked_draws_todays_hero(value):
    p = page(staked=value)
    no_line(p)
    assert outline(hero(p)) == outline(hero(page()))


@needs_node
def test_no_bets_no_line():
    p = page(staked={"all": 0.0, "bets": 0, "since": None, "day": 0.0, "settled": 0.0, "profit": 0.0})
    no_line(p)
    assert outline(hero(p)) == outline(hero(page()))


@needs_node
def test_with_the_line_every_word_of_todays_live_tab_is_still_there():
    gone = missing(page(staked=STAKED))
    assert not gone, f"words of today's Live tab gone with the staked line: {list(gone.items())[:40]}"
