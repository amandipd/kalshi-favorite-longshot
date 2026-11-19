"""The +1¢ limit, on paper: the Live Research tab's first card, and "How it trades" while the live limit is off.

No real money on the +1¢ limit yet. Real orders go back to an immediate-or-cancel limit at exactly
the ask the bot saw (it takes what the book offers at once, never paying more, and cancels the rest). Right after each
real order the bot reads the book again and measures, on paper, what a limit 1¢ higher would have bought: the "shadow"
table, which the dashboard sends as the reply's "shadow" block. On the page that becomes a card of its own, first in
the tab, before the live +1¢ card:

- what share of the contracts asked for really filled, and what share would have with the extra cent;
- the extra contracts (the ones only the extra cent would have bought), the share of the unfilled ones they'd have
  caught, their average price, how often they won against the win rate they need to break even (price plus fee), their
  P&L, and their ¢ per $10 staked with its 95% range;
- how long after minute 8 the book was read, and one caveat in plain words: the book is read a moment after the real
  order, so offers may have gone or arrived meanwhile, and it can't show whether other traders would have beaten the
  bot to them;
- the research's predictions beside those paper numbers, and the latest paper measurements, one row per order.

With the live limit off (LIMIT_UP 0) the live card shows only its status and the fill rates: every order is in the
"before" arm, so its other panels would be empty. "How it trades" says the order goes at the best price it just saw,
and that the +1¢ is measured on paper; once LIMIT_UP is set above 0 it says the limit sits that much over the ask.

dashboard.html is read as text and its method() run in node; live_research.js is loaded whole in node with the page's
globals, as test_live_research_page.py does (its harness is reused here), and handed replies built by hand in the
server's shape. The node tests skip themselves without node.

    python -m pytest tests/test_shadow_page.py -q
"""

import json
import re
import subprocess

import pytest

from test_folds_live import fold_helper
from test_live_research_page import (BEFORE, FULL, NODE, NOW, POISON, SCRIPT, WAITING, body, card, code, esc, group,
                                     h3s, has_num, is_about, needs_node, norm, own, piece, run, share, shows, text, with_)

PAPER_HEAD, ROWS_HEAD = "The +1¢ limit, on paper", "Latest paper measurements"


# ------------------------------------------------------------------ replies shaped like /api/live-research, with "shadow"
SH_STARTED = NOW - 5 * 3600 - 20 * 60       # the first paper measurement, 11:20 AM: the bot restarted this morning
SH_ROWS = [   # newest first
    {"ts": NOW - 140, "ticker": "KXBTC15M-26OCT111645-45", "side": "yes", "seen": 0.93, "limit": 0.94, "asked": 23.0,
     "filled": 17.0, "extra": 6.0, "avgPrice": 0.9367, "lag": 2.2, "result": "open"},
    {"ts": NOW - 1040, "ticker": "KXETH15M-26OCT111630-30", "side": "no", "seen": 0.957, "limit": 0.967, "asked": 31.0,
     "filled": 0.0, "extra": 0.0, "avgPrice": None, "lag": 3.1, "result": "lost"},        # the extra cent caught nothing
    {"ts": NOW - 1940, "ticker": "KXSOL15M-26OCT111615-15", "side": "yes", "seen": 0.951, "limit": 0.961, "asked": 29.0,
     "filled": 12.0, "extra": 9.0, "avgPrice": 0.9583, "lag": 1.9, "result": "won"},
    {"ts": NOW - 2840, "ticker": "KXXRP15M-26OCT111600-00", "side": "no", "seen": 0.912, "limit": 0.922, "asked": 44.0,
     "filled": 38.0, "extra": 0.0, "avgPrice": None, "lag": 2.7, "result": "open"},        # nothing dearer within 1¢
]
# The extra contracts: 287 of them, 95.6¢ on average, break-even 97.2%, won 98.4%, +$3.87, +7.4¢ per $10 (−4.2 to +19.0)
SH_GROUP = group(139, 287.0, 0.9562, 4.62, 0.9562 + 4.62 / 287, 251.0, 247.0, 247 / 251, 3.87, 240.3, 7.4, 11.6 / 1.96, 58)
SH_TOO_EARLY_TEXT = "Too early to tell: 412 of 1000 orders measured on paper so far."
SHADOW = {"limitUp": 0.01, "started": SH_STARTED, "target": 1000, "orders": 412, "unread": 7, "asked": 1840.0,
          "filled": 1030.0, "extra": 287.0, "fillShare": 1030 / 1840, "fillShareWith": (1030 + 287) / 1840,   # 56.0%, 71.6%
          "remaining": 810.0, "extraShare": 287 / 810, "ordersWithExtra": 139, "lag": 2.4,                     # 35.4%
          "group": SH_GROUP, "verdict": {"state": "too-early", "text": SH_TOO_EARLY_TEXT, "orders": 412, "target": 1000},
          "rows": SH_ROWS}
SH_WAITING_TEXT = "Not recording yet: the bot measures the paper +1¢ from its next restart."
SH_WAITING = {"limitUp": 0.01, "started": None, "target": 1000, "orders": 0, "unread": 0, "asked": 0.0, "filled": 0.0,
              "extra": 0.0, "fillShare": None, "fillShareWith": None, "remaining": 0.0, "extraShare": None,
              "ordersWithExtra": 0, "lag": None, "group": group(),
              "verdict": {"state": "waiting", "text": SH_WAITING_TEXT, "orders": 0, "target": 1000}, "rows": []}
SH_VERDICTS = [
    ("waiting", SH_WAITING_TEXT),
    ("too-early", SH_TOO_EARLY_TEXT),
    ("helping", "On paper the extra cent pays: the extra contracts made money, and their 95% range is above zero."),
    ("hurting", "On paper the extra cent loses money: the extra contracts' 95% range is below zero."),
    ("no-difference", "No clear difference on paper: the extra contracts' 95% range includes zero."),
]

# Today's reply: the live limit is off (LIMIT_UP 0, nothing started), the paper card has numbers.
OFF_TEXT = "Off: real orders go at the ask the bot saw. The paper +1¢ above measures the extra cent without real money."
LIVE_OFF = with_(WAITING, limitUp=0.0, fillsRecorded=True,
                 verdict={"state": "off", "text": OFF_TEXT, "orders": 0, "target": 1000})
TODAY = {**LIVE_OFF, "shadowUp": 0.01, "shadow": SHADOW}
# Later: the +1¢ live too (LIMIT_UP 0.01), both cards with numbers.
BOTH_ON = {**FULL, "shadowUp": 0.01, "shadow": SHADOW}


# ------------------------------------------------------------------ helpers
def drawn(*replies):
    """Each reply drawn by liveResearchHtml(): pure (no element, fetch, timer or drawing), and no missing number reaching
    the page as NaN, undefined, null or Infinity."""
    out = run(replies=replies)["html"]
    for h in out:
        assert isinstance(h["markup"], str) and h["markup"].strip(), "liveResearchHtml() returned nothing"
        assert not [c for c in h["calls"] if c in ("$", "patch", "fetch", "setInterval", "setTimeout")
                    or c.startswith("document.")], h["calls"]
        bad = re.search(r"\b(NaN|undefined|null|Infinity)\b", text(h["markup"]))
        assert not bad, f"a missing number reached the page as {bad.group(0)!r}"
    return [h["markup"] for h in out]


def paper(markup):
    """The paper card, whose first heading is its name."""
    c = card(markup, "shadow")
    found = [t for _, t in h3s(c)]
    assert found and found[0] == PAPER_HEAD, found
    return c


def rows_panel(c):
    """The card's "Latest paper measurements": from that h3 to the card's next h3, or its end."""
    found = h3s(c)
    at = next((a for a, t in found if t == ROWS_HEAD), None)
    assert at is not None, f"no <h3>{ROWS_HEAD}</h3> in the paper card; its headings are {[t for _, t in found]}"
    return c[at:min((a for a, _ in found if a > at), default=len(c))]


def summary(c):
    """The paper card without its rows: the numbers the latest measurements can't stand in for."""
    return c.replace(rows_panel(c), "", 1)


def tr_with(markup, needle):
    """The table row holding needle (a ticker)."""
    found = [r for r in re.findall(r"<tr\b.*?</tr>", markup, re.S) if needle in r]
    assert len(found) == 1, f"{len(found)} rows hold {needle!r}"
    return found[0]


def secs(markup, v):
    """v seconds, to one or two places: "2.4 s", "2.40s", "2.4 sec"."""
    t = text(markup)
    return any(re.search(rf"(?<![\d.]){re.escape(w)}\s?s(ec(ond)?s?)?\b", t) for w in (f"{v:.1f}", f"{v:.2f}"))


def prices(markup):
    """Every price in cents the markup shows, e.g. {"93¢", "95.7¢"}."""
    return set(re.findall(r"(?<![\d.])\d+(?:\.\d)?¢", text(markup)))


# ------------------------------------------------------------------ dashboard.html and live_research.js, read as text
def test_the_paper_card_comes_first_in_the_list_of_cards():
    assert "const CARDS = [shadowCard, " in code(own("live_research.js"))   # first; the fast entry and live cards follow


def test_the_pages_fallback_limits_have_the_live_limit_off_and_the_paper_one_a_cent_over():
    """Until the server says: live at the ask it saw (limitUp 0), on paper 1¢ over it (shadowUp 0.01)."""
    limits = re.search(r"const LIMITS = \{(.*?)\};", SCRIPT, re.S).group(1)
    assert re.search(r"\blimitUp: 0(?:\.0+)?(?![.\d])", limits), limits
    assert re.search(r"\bshadowUp: 0\.01(?!\d)", limits), limits


def test_how_it_trades_has_a_sentence_for_the_live_limit_on_and_one_for_it_off():
    m = body("function method(L) {")
    templates = m.split("`")
    assert "L.limitUp > 0" in m                                                   # on only once the bot sets LIMIT_UP
    on = "${cents(L.limitUp)} over the best price it just saw on the book (at most ${cents(L.hi)})"
    assert any(on in x and "immediate-or-cancel" in x for x in templates)         # the sentence it has now
    assert any("limit order at the best price it just saw on the book: it never pays more" in x
               and "immediate-or-cancel" in x for x in templates)                 # off: at the ask it saw
    assert any("${cents(L.shadowUp)} higher would have bought" in x for x in templates)   # ... and the paper +1¢


# ------------------------------------------------------------------ "How it trades", run in node
METHOD_RUNNER = """
"use strict";
const __in = JSON.parse(require("fs").readFileSync(0, "utf8"));
const __out = [];
let data = { groups: ["BTC", "ETH"] };
function patch(id, html) { __out.push([id, html]); }
%s
for (const l of __in) method(Object.assign({}, LIMITS, l || {}));   // as render() does: L = Object.assign({}, LIMITS, d.limits)
process.stdout.write(JSON.stringify(__out));
"""

OFF_SENTENCE = ("An immediate-or-cancel limit order at the best price it just saw on the book: it never pays more, and "
                "nothing waits on the book.")
PAPER_SENTENCE = "On paper it also measures what a limit {} higher would have bought (the Live Research tab)."
ON_SENTENCE = ("An immediate-or-cancel limit order 1¢ over the best price it just saw on the book (at most 99.9¢): it takes "
               "the cheapest offers first, never pays more than that limit, and nothing waits on the book.")


def how_it_trades(*limits):
    """What "How it trades" says for each set of limits the server sends (None: none, so the page's own defaults)."""
    if not NODE:
        pytest.skip("node isn't installed")
    js = "\n".join([*(piece(rf"^const {n} = [^\n]*$") for n in ("esc", "pct", "limitPct", "cents")),
                    fold_helper(SCRIPT),   # How it trades draws inside a fold once the Live tab folds (empty before that)
                    piece(r"^const LIMITS = \{.*?\};"), piece(r"^function method\(L\) \{.*?^\}$")])
    r = subprocess.run([NODE, "-e", METHOD_RUNNER % js], input=json.dumps(list(limits)), capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert [i for i, _ in out] == ["method"] * len(limits)
    return [m for _, m in out]


@needs_node
def test_with_the_live_limit_off_how_it_trades_says_the_ask_it_saw_and_the_paper_cent():
    for m in how_it_trades({"limitUp": 0.0, "shadowUp": 0.01}, None):          # None: the page's defaults say the same
        assert shows(m, OFF_SENTENCE) and shows(m, PAPER_SENTENCE.format("1¢")), text(m)
        assert "over the best price" not in text(m)


@needs_node
def test_the_paper_cent_in_how_it_trades_is_the_one_the_server_sends():
    m = how_it_trades({"limitUp": 0.0, "shadowUp": 0.02})[0]
    assert shows(m, PAPER_SENTENCE.format("2¢")), text(m)


@needs_node
def test_with_the_live_limit_on_how_it_trades_says_a_cent_over_the_ask_and_nothing_about_paper():
    m = how_it_trades({"limitUp": 0.01, "shadowUp": 0.01})[0]
    assert shows(m, ON_SENTENCE), text(m)
    assert "On paper" not in text(m) and "at the best price it just saw on the book:" not in text(m)


# ------------------------------------------------------------------ the paper card: where it sits, and its verdict
@needs_node
@pytest.mark.parametrize("reply", [TODAY, BOTH_ON], ids=["live-off", "live-on"])
def test_the_paper_card_comes_before_the_live_card_headed_by_its_name(reply):
    m = drawn(reply)[0]
    opening = '<article class="lr-card" data-exp="shadow">'
    assert opening in m and m.index(opening) < m.index('data-exp="limitup"')
    assert m.index(opening) == m.index("<article")                              # the first card on the tab
    assert ROWS_HEAD in [t for _, t in h3s(paper(m))]


@needs_node
def test_the_paper_card_shows_its_verdict_escaped_how_far_along_and_when_it_started():
    early = 'Too early to tell: "paper" <so far> & counting.'                    # needs escaping, and says no count itself
    reply = with_(TODAY, shadow__verdict__text=early, shadow__verdict__orders=37, shadow__orders=37)
    out = run(replies=[reply], times=[SH_STARTED])
    m, (when_, hhmm_) = out["html"][0]["markup"], out["times"][0]
    c = paper(m)
    assert esc(early) in c and "<so far>" not in m
    assert re.search(r"(?<![\d.,])37\s*(?:of|/)\s*1,?000(?![\d,])", text(summary(c))), text(c)   # n of the target
    assert norm(when_) in text(summary(c)) or norm(hhmm_) in text(summary(c))    # when the first measurement was made


@needs_node
@pytest.mark.parametrize("state, words", SH_VERDICTS, ids=[s for s, _ in SH_VERDICTS])
def test_every_paper_verdict_is_shown_as_the_server_words_it(state, words):
    shadow = SH_WAITING if state == "waiting" else SHADOW
    reply = with_({**TODAY, "shadow": shadow}, shadow__verdict__state=state, shadow__verdict__text=words)
    assert esc(words) in paper(drawn(reply)[0])


@needs_node
def test_an_unknown_verdict_state_is_shown_escaped_on_either_card():
    odd = "zzz <i>new</i>"
    m = drawn(with_(BOTH_ON, shadow__verdict__state=odd, verdict__state=odd))[0]
    assert esc(odd) in paper(m) and esc(odd) in card(m, "limitup") and "<i>new</i>" not in m
    assert esc(SH_TOO_EARLY_TEXT) in paper(m)                                   # the rest of the card is still drawn


@needs_node
@pytest.mark.parametrize("shadow", [None, "missing"], ids=["null", "missing"])
def test_without_a_shadow_table_the_card_says_it_isnt_recording_yet(shadow):
    """null: a ledger from before the restart. Missing: a dashboard not restarted since the key was added."""
    reply = dict(LIVE_OFF) if shadow == "missing" else {**LIVE_OFF, "shadowUp": 0.01, "shadow": None}
    t = text(paper(drawn(reply)[0]))
    assert re.search(r"\b(isn[’']t|is not|not) recording\b", t, re.I), t
    assert re.search(r"next restart", t, re.I), t


# ------------------------------------------------------------------ the paper card: its numbers
@needs_node
def test_it_shows_the_real_fill_share_and_the_share_with_the_extra_cent():
    s = summary(paper(drawn(TODAY)[0]))
    assert share(s, 1030 / 1840) and share(s, 1317 / 1840), text(s)           # 56.0%, 71.6%


@needs_node
def test_it_shows_the_extra_contracts_and_the_share_of_the_unfilled_ones_they_would_have_caught():
    s = summary(paper(drawn(TODAY)[0]))
    assert has_num(s, 287) and share(s, 287 / 810), text(s)                    # 287 contracts, 35.4% of the 810 unfilled


@needs_node
def test_it_shows_the_extra_contracts_price_win_rate_against_break_even_and_pnl():
    s = summary(paper(drawn(TODAY)[0]))
    assert shows(s, "95.6¢"), text(s)                                           # their average price
    assert share(s, 247 / 251) and share(s, 0.9562 + 4.62 / 287), text(s)      # won 98.4%, needs 97.2%
    assert shows(s, "+$3.87"), text(s)


@needs_node
def test_it_shows_cents_per_ten_dollars_with_its_95_range_in_the_live_cards_form():
    s = summary(paper(drawn(TODAY)[0]))
    assert shows(s, "+7.4¢") and shows(s, "(−4.2 to +19.0)"), text(s)         # perTen ± 1.96·se, with a real minus sign
    assert "(-4.2" not in text(s)


@needs_node
def test_it_says_how_long_after_minute_8_the_book_was_read():
    s = summary(paper(drawn(TODAY)[0]))
    assert secs(s, 2.4) and "after minute 8" in text(s), text(s)


@needs_node
def test_it_says_in_plain_words_what_paper_cant_show():
    """The book is read a moment after the real order, so offers may have gone or arrived; and it can't show whether
    other traders would have beaten the bot to them."""
    t = text(summary(paper(drawn(TODAY)[0])))
    assert re.search(r"\b(a moment|moments|right|just|shortly) after\b", t, re.I), t
    assert re.search(r"\bbeat(en)?\b", t, re.I), t


@needs_node
def test_the_research_predictions_sit_beside_the_paper_numbers():
    s = summary(paper(drawn(TODAY)[0]))
    assert share(s, 0.4321) and share(s, 0.6018) and share(s, 0.7349)          # history: fills before, and with +1¢
    assert share(s, 0.5462) and share(s, 0.9413)                                # the live-fills replay
    with_cent = [r for r in re.findall(r"<tr\b.*?</tr>", s, re.S) if share(r, 0.6018) and share(r, 0.7349)]
    assert with_cent and share(with_cent[0], 1317 / 1840), "the predicted fill with +1¢ isn't beside the paper's"
    extra = [r for r in re.findall(r"<tr\b.*?</tr>", s, re.S) if re.search(r"9\.6\b", text(r)) and re.search(r"13\.7\b", text(r))]
    assert extra and shows(extra[0], "+7.4¢"), "the predicted ¢ per $10 of the extra contracts isn't beside the paper's"


@needs_node
def test_a_missing_prediction_says_its_unavailable_on_the_paper_card_too():
    m = drawn(with_(TODAY, predictions={"history": None, "live": None}))[0]
    assert re.search(r"unavailable|not available", text(summary(paper(m))), re.I)


# ------------------------------------------------------------------ the paper card: its latest measurements
@needs_node
def test_the_latest_paper_measurements_show_each_order_newest_first():
    rows = rows_panel(paper(drawn(TODAY)[0]))
    at = [rows.find(r["ticker"]) for r in SH_ROWS]
    assert -1 not in at and at == sorted(at), at


@needs_node
@pytest.mark.parametrize("r", SH_ROWS, ids=[r["ticker"].split("-")[0] for r in SH_ROWS])
def test_each_paper_measurement_shows_what_it_saw_its_limit_what_filled_the_extra_and_how_it_did(r):
    row = tr_with(rows_panel(paper(drawn(TODAY)[0])), r["ticker"])
    seen, limit = (f"{v * 100:g}¢" for v in (r["seen"], r["limit"]))           # 93¢, 95.7¢ ...
    assert shows(row, seen) and shows(row, limit), text(row)
    for n in (r["asked"], r["filled"], r["extra"]):                             # asked, really filled, extra on paper
        assert has_num(row, int(n)), (n, text(row))
    if r["extra"]:
        assert shows(row, f"{r['avgPrice'] * 100:.1f}¢"), text(row)             # what the extra contracts cost
    else:
        assert prices(row) <= {seen, limit, "1¢"}, text(row)                     # no extra contracts: no price for them
    assert secs(row, r["lag"]), text(row)                                       # when the book was read
    assert re.search(rf"\b{r['result']}\b", text(row), re.I), text(row)


# ------------------------------------------------------------------ the live card with the live limit off
@needs_node
@pytest.mark.parametrize("reply", [TODAY, {**LIVE_OFF, "shadowUp": 0.01, "shadow": None}], ids=["paper-on", "paper-not-yet"])
def test_with_the_live_limit_off_its_card_shows_only_its_status_and_fill_rates(reply):
    live = card(drawn(reply)[0], "limitup")
    found = [t for _, t in h3s(live) if not is_about(t)]                       # its "How it's measured" fold is part of its status
    assert found[:2] == ["The +1¢ limit experiment", "Fill rates"], found
    for gone in ("What the extra cent bought", "Predictions vs live", "Latest experiment orders"):
        assert gone not in found, found
    assert esc(OFF_TEXT) in live
    for n in (523, 800, 440, 101, 57, 365):                                     # every order so far is in the before arm
        assert has_num(live, n), n
    assert share(live, BEFORE["fillShare"])


# ------------------------------------------------------------------ nothing breaks, nothing leaks
SPARSE_ROWS = [{**SH_ROWS[0], "avgPrice": None, "lag": None, "result": None}, {"ticker": "KXDOGE15M-26OCT111645-45"}]
ODD = [
    ("today", TODAY),
    ("both-on", BOTH_ON),
    ("paper-waiting", {**TODAY, "shadow": SH_WAITING}),
    ("paper-null", {**LIVE_OFF, "shadowUp": 0.01, "shadow": None}),
    ("paper-missing", LIVE_OFF),
    ("paper-empty", {**TODAY, "shadow": {}}),
    ("no-range-yet", with_(TODAY, shadow__group__se=None, shadow__group__windows=1)),
    ("sparse-rows", with_(TODAY, shadow__rows=SPARSE_ROWS)),
    ("no-group", with_(TODAY, shadow__group=None)),
    ("no-verdict", with_(TODAY, shadow__verdict=None)),
    ("predictions-null", with_(TODAY, predictions=None)),
    ("predictions-missing", {k: v for k, v in TODAY.items() if k != "predictions"}),
]


@needs_node
@pytest.mark.parametrize("reply", [r for _, r in ODD], ids=[i for i, _ in ODD])
def test_the_paper_card_is_drawn_without_a_missing_number_showing(reply):
    paper(drawn(reply)[0])


@needs_node
def test_every_server_string_on_the_paper_card_is_escaped():
    """Tickers, sides, results, the verdict and the prediction sources come from the server: none may reach the markup
    raw, and a number that arrives as text mustn't either."""
    ticker = "KX" + POISON + "15M-26OCT111645-45"
    strings = [with_(TODAY, shadow__rows__0__ticker=ticker), with_(TODAY, shadow__verdict__text="Too early " + POISON),
               with_(TODAY, shadow__verdict__text=POISON, shadow__verdict__state=POISON, shadow__rows__0__ticker=ticker,
                     shadow__rows__0__side=POISON, shadow__rows__0__result=POISON, predictions__history__source=POISON,
                     predictions__live__source=POISON)]
    for m in drawn(*strings):
        assert "<img" not in m.lower()
        assert esc(POISON) in paper(m)                                          # shown, as text
    numbers = with_(TODAY, shadow__started=POISON, shadow__lag=POISON, shadow__fillShare=POISON, shadow__target=POISON,
                    shadow__verdict__orders=POISON, shadow__group__avgPrice=POISON, shadow__group__perTen=POISON,
                    shadow__rows__0__seen=POISON, shadow__rows__0__avgPrice=POISON, shadow__rows__0__lag=POISON)
    m = run(replies=[numbers])["html"][0]["markup"]
    assert "<img" not in m.lower()
