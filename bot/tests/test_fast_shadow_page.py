"""Fast entry, on paper: the Live Research tab's card for orders sent at minute 8 exactly (live_research.js).

The live bot's minute-8 orders land a median 2.4 s after minute 8 starts, by when other traders have taken much of the
volume at its limit. Without real money, a background reader (fast_entry.MarkReader) reads every order book of the
window at minute 8 exactly (480.0 s into the window, on Kalshi's clock: "the mark"), and the bot pairs each real order
with a paper twin measured on the mark's book: what an order sent that instant, with the same limit rule, would have
bought. The ledger keeps those as the shadow table's kind 'fast' rows; the dashboard sends them as the reply's
"fastShadow" block. On the page that becomes a card of its own, between the paper +1¢ card and the live +1¢ one:

- its name, the server's verdict in its own words with a chip, how far along it is (orders paired of the target),
  when it started, and how soon after minute 8 the mark's book answered (the median and the 90th percentile);
- one caveat in plain words: this is the best case, since other traders' orders land 10-30 ms after minute 8 and one
  from this PC about 0.1-0.2 s after it, by when some offers may be gone;
- real orders against orders at minute 8: fill shares, the difference in percentage points with its 95% range, the
  share of the real misses the mark's book had, the asks seen, the prices paid, and the P&L and ¢ per $10 of each;
- the latest pairs, one row per real order and its paper twin, newest first.

Without the block (a ledger from before the restart, a dashboard not restarted since, or an answer of another shape)
the card still stands, saying it isn't recording yet. live_research.js is loaded whole in node with the page's globals,
as test_live_research_page.py does (its harness is reused here, with one addition: replies may carry NaN and Infinity,
which JSON can't, so the runner turns marker strings into them), and handed replies built by hand in the server's
shape. The node tests skip themselves without node.

    python -m pytest tests/test_fast_shadow_page.py -q
"""

import json
import os
import re
import subprocess

import pytest

from test_live_research_page import (HEADING, NODE, NOW, POISON, RUNNER, card, code, esc, h3s, has_num, is_about,
                                     needs_node, norm, own, page_globals, share, shows, text, with_)
from layout import STATIC
from test_shadow_page import PAPER_HEAD, TODAY

HERE = STATIC   # the dashboard's pages: dashboard.html, tape.html and their .js and .css
FAST_HEAD, VERSUS_HEAD, PAIRS_HEAD = "Fast entry, on paper", "Real orders against orders at minute 8", "Latest pairs"
HOSTILE = """<script>alert("x")</script> & 'q'"""

# What the server says for each verdict state (dashboard.py's FAST_SAYS), and how its chip reads here.
FAST_SAYS = {
    "waiting": "Not recording yet: the bot reads the order books at minute 8 exactly from its next restart.",
    "too-early": "Too early to tell: {n} of {target} orders paired on paper so far.",
    "faster-fills-more": "Orders sent at minute 8 exactly would fill more: the difference's 95% range is above zero.",
    "faster-fills-less": "Orders sent at minute 8 exactly would fill less: the difference's 95% range is below zero.",
    "no-difference": "No clear difference in fills: the difference's 95% range includes zero."}
NOT_RECORDING = FAST_SAYS["waiting"]
CHIPS = [   # state, the chip's words, its tone class (None: no tone)
    ("waiting", "Not recording", None),
    ("too-early", "Too early to tell", "warn"),
    ("faster-fills-more", "▲ Fills more", "up"),
    ("faster-fills-less", "▼ Fills less", "down"),
    ("no-difference", "No clear difference", None),
]
TONES = {"up", "down", "warn", "part", "yes", "no"}   # the state classes the tab already uses beside its .lr- ones
FOLD_CLASSES = {"fold", "fold-h", "fold-t", "fold-b", "chev", "fold-m", "fold-body"}   # the shared fold's

# JSON can't carry NaN or Infinity, so a reply carries these markers and the runner turns them into the real thing.
NAN, INF, NEG_INF, THROWS = "__NaN__", "__Infinity__", "__-Infinity__", "__Throws__"
REVIVE = ('const __revive = (k, v) => v === "__NaN__" ? NaN : v === "__Infinity__" ? Infinity : v === "__-Infinity__" ? -Infinity'
          ' : v === "__Throws__" ? new Proxy({}, { get() { throw new Error("<b>boom</b>"); } }) : v;\n')


# ------------------------------------------------------------------ replies shaped like /api/live-research, with "fastShadow"
FS_STARTED = NOW - 3 * 3600 - 10 * 60      # the first pair, 1:30 PM: the bot restarted this afternoon
FS_ROWS = [   # newest first
    # a limit over the ask at the mark (as if LIMIT_UP were 1¢), so the limit's column can be told from the ask's
    {"ts": NOW - 150, "ticker": "KXBTC15M-26OCT111645-45", "side": "yes", "seenReal": 0.94, "seen": 0.92, "limit": 0.93,
     "asked": 23.0, "filled": 9.0, "extra": 21.0, "avgPrice": 0.9238, "lag": 0.31, "pnl": None, "result": "open"},
    {"ts": NOW - 1050, "ticker": "KXETH15M-26OCT111630-30", "side": "no", "seenReal": 0.957, "seen": 0.951, "limit": 0.951,
     "asked": 31.0, "filled": 0.0, "extra": 14.0, "avgPrice": 0.9536, "lag": 0.44, "pnl": -13.47, "result": "lost"},
    {"ts": NOW - 1950, "ticker": "KXSOL15M-26OCT111615-15", "side": "yes", "seenReal": 0.951, "seen": None, "limit": None,
     "asked": 29.0, "filled": 12.0, "extra": 0.0, "avgPrice": None, "lag": 0.58, "pnl": 0.0, "result": "won"},   # no offers at the mark
    {"ts": NOW - 2850, "ticker": "KXXRP15M-26OCT111600-00", "side": "no", "seenReal": 0.912, "seen": 0.885, "limit": None,
     "asked": 44.0, "filled": 38.0, "extra": 0.0, "avgPrice": None, "lag": 0.52, "pnl": 0.0, "result": "won"},    # under the band
]
FS_TOO_EARLY_TEXT = FAST_SAYS["too-early"].format(n=184, target=300)
# 184 pairs: real orders filled 55.0% of 5,000 contracts, at minute 8 67.3%: +12.3 pts, 95% range +4.1 to +20.5
FAST = {"started": FS_STARTED, "target": 300, "orders": 184, "unread": 7, "asked": 5000.0, "filled": 2750.0, "extra": 3366.0,
        "realShare": 0.55, "fastShare": 0.6732, "diff": 0.6732 - 0.55, "diffSe": 0.0821 / 1.96,
        "caught": 616 / 2250, "realSeen": 0.9514, "fastSeen": 0.9468, "realAvg": 0.9532, "fastAvg": 0.9479,   # 27.4%
        "lag": {"median": 0.37, "p90": 0.83},
        "pnl": {"settled": 151, "paper": {"pnl": 9.87, "staked": 1050.0, "perTen": 9.4, "se": 6.2 / 1.96},    # +3.2 to +15.6
                "real": {"pnl": 4.12, "staked": 675.41, "perTen": 6.1, "se": 5.3 / 1.96}},                      # +0.8 to +11.4
        "verdict": {"state": "too-early", "text": FS_TOO_EARLY_TEXT, "orders": 184, "target": 300},
        "rows": FS_ROWS}
# Restarted, no window yet: the shadow table is there but holds no 'fast' row.
NOTHING = {"pnl": 0.0, "staked": 0.0, "perTen": None, "se": None}
FS_WAITING = {"started": None, "target": 300, "orders": 0, "unread": 0, "asked": 0.0, "filled": 0.0, "extra": 0.0,
              "realShare": None, "fastShare": None, "diff": None, "diffSe": None, "caught": None, "realSeen": None,
              "fastSeen": None, "realAvg": None, "fastAvg": None, "lag": {"median": None, "p90": None},
              "pnl": {"settled": 0, "paper": NOTHING, "real": NOTHING},
              "verdict": {"state": "waiting", "text": NOT_RECORDING, "orders": 0, "target": 300}, "rows": []}

FAST_REPLY = {**TODAY, "fastShadow": FAST}          # today's reply: the paper +1¢ measuring, the live +1¢ off
WAITING_REPLY = {**TODAY, "fastShadow": FS_WAITING}
NOT_YET = {**TODAY, "fastShadow": None}             # a ledger from before the restart: no shadow table


# ------------------------------------------------------------------ running it
def run(replies=(), times=()):
    """liveResearchHtml() on each reply in node, with the page's globals (test_live_research_page.py's harness), the
    markers above turned into NaN, Infinity or an object that throws, and when()/hhmm() of each time."""
    if not NODE:
        pytest.skip("node isn't installed")
    own("live_research.js")
    js, parse = page_globals(), "const __in = JSON.parse(__input);"
    assert parse in js, "test_live_research_page.py's page_globals() no longer parses its input that way: update run()"
    payload = {"pageJs": js.replace(parse, REVIVE + "const __in = JSON.parse(__input, __revive);", 1),
               "file": os.path.join(HERE, "live_research.js"), "replies": list(replies), "page": "account", "data": None,
               "fetches": [], "steps": [], "times": list(times), "lrHidden": False}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def drawn(*replies):
    """Each reply's markup."""
    out = [h["markup"] for h in run(replies=replies)["html"]]
    for m in out:
        assert isinstance(m, str) and m.strip(), "liveResearchHtml() returned nothing"
    return out


def fast(markup):
    """The fast-entry card, whose first heading is its name, and which shows no missing number as NaN, undefined, null
    or Infinity, in its words or its attributes."""
    c = card(markup, "fastshadow")
    found = [t for _, t in h3s(c)]
    assert found and found[0] == FAST_HEAD, found
    for where, s in (("words", text(c)), ("markup", c)):
        bad = re.search(r"\b(NaN|undefined|null|Infinity)\b", s)
        assert not bad, f"a missing number reached the card's {where} as {bad.group(0)!r}"
    return c


def panel_of(c, heading):
    """A panel of the card: from its heading to the card's next one, or its end. The card's "How it's measured" fold
    (its explanations and caveat) is part of the card's head, so it doesn't end a panel."""
    found = [(a, t) for a, t in h3s(c) if not is_about(t)]
    at = next((a for a, t in found if t == heading), None)
    assert at is not None, f"no <h3>{heading}</h3> in the fast card; its headings are {[t for _, t in found]}"
    return c[at:min((a for a, _ in found if a > at), default=len(c))]


def headers(c, title):
    """Each panel headed `title`: its heading and, for a fold, the rest of its header (the meta beside the title)."""
    out = []
    for m in re.finditer(HEADING, c, re.S):
        if [t for _, t in h3s(m.group(0))] == [title]:
            end = c.find('class="fold-body"', m.end()) if m.group(0).startswith("<h2") else -1
            out.append(c[m.start():end] if end > 0 else m.group(0))
    return out


def chip(c):
    """The card's first chip, its verdict: its classes and its markup."""
    m = re.search(r'<span\b[^>]*\bclass="([^"]*\blr-chip\b[^"]*)"[^>]*>(.*?)</span>', c, re.S)
    assert m, "no chip on the fast card"
    return set(m.group(1).split()), m.group(2)


def kpis(c):
    """Each figure of the card's head, by its label: "Started" -> what it says."""
    out = {}
    for m in re.finditer(r'<div\b[^>]*\bclass="lr-kpi"[^>]*>(.*?)</div>', c, re.S):
        k = re.search(r'<span\b[^>]*\bclass="lr-k"[^>]*>(.*?)</span>', m.group(1), re.S)
        if k:
            out[text(k.group(1)).strip()] = text(m.group(1))
    return out


def tr_with(markup, needle):
    """The one table row whose words hold needle."""
    found = [r for r in re.findall(r"<tr\b.*?</tr>", markup, re.S) if needle in text(r)]
    assert len(found) == 1, f"{len(found)} rows hold {needle!r}"
    return found[0]


def cells(tr):
    """A row's cells, th or td, as words."""
    return [text(x) for x in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S)]


def c_(v):
    """A price as the page's cents() writes it: 93¢, 95.7¢."""
    x = v * 100
    return f"{round(x)}¢" if abs(x - round(x)) < 0.05 else f"{x:.1f}¢"


def has_price(markup, p):
    return any(re.search(rf"(?<![\d.]){re.escape(p)}", t) for t in (text(markup), re.sub(r"<[^>]+>", "", markup)))


def prices(markup):
    """Every price in cents the markup shows, e.g. {"93¢", "95.7¢"}."""
    return set(re.findall(r"(?<![\d.])\d+(?:\.\d)?¢", text(markup)))


def has_secs(markup, v):
    """v seconds, to one place: "0.4 s"."""
    return re.search(rf"(?<![\d.]){re.escape(f'{v:.1f}')}\s?s\b", text(markup)) is not None


def classes(markup):
    """Every class named in the markup's class attributes."""
    return {k for v in re.findall(r'\bclass="([^"]*)"', markup) for k in v.split()}


# ------------------------------------------------------------------ live_research.js, read as text
def test_the_fast_card_sits_between_the_paper_card_and_the_live_one_in_the_list():
    assert "const CARDS = [shadowCard, fastShadowCard, limitCard];" in code(own("live_research.js"))


def test_the_files_header_names_the_fast_entry_card():
    head = re.match(r"\s*/\*(.*?)\*/", own("live_research.js"), re.S)
    assert head and "Fast entry" in head.group(1), "the header comment has no entry for the fast-entry card"


# ------------------------------------------------------------------ where it sits, and before it records
@needs_node
@pytest.mark.parametrize("reply", [FAST_REPLY, NOT_YET], ids=["recording", "not-yet"])
def test_the_cards_run_paper_then_fast_entry_then_the_live_one(reply):
    m = drawn(reply)[0]
    assert re.findall(r'<article\b[^>]*\bdata-exp="([^"]*)"', m) == ["shadow", "fastshadow", "limitup"]
    fast(m)
    assert [t for _, t in h3s(card(m, "shadow"))][0] == PAPER_HEAD


@needs_node
@pytest.mark.parametrize("value", [None, "missing", "recording soon", [1, 2], 5, True],
                         ids=["null", "missing", "string", "list", "number", "bool"])
def test_without_a_fast_block_the_card_says_it_isnt_recording_yet_and_the_others_are_untouched(value):
    """null: a ledger with no shadow table yet. Missing: a dashboard not restarted since the key was added. Anything
    else that isn't an object: an answer of another shape."""
    reply = dict(TODAY) if value == "missing" else {**TODAY, "fastShadow": value}
    base, m = drawn(TODAY, reply)
    c = fast(m)
    cls, label = chip(c)
    assert text(label).strip() == "Not recording" and not cls & {"up", "down", "warn"}, (cls, label)
    assert shows(c, NOT_RECORDING), text(c)
    for exp in ("shadow", "limitup"):                                           # drawn exactly as without the key
        assert card(m, exp) == card(base, exp), exp


@needs_node
@pytest.mark.parametrize("reply", [FAST_REPLY, NOT_YET, WAITING_REPLY], ids=["recording", "not-yet", "waiting"])
def test_its_lede_says_in_plain_words_what_it_measures(reply):
    """Real orders keep their timing (about 2.4 s after minute 8); in the background the bot reads every book at minute
    8 exactly (480.0 s into the window, on Kalshi's clock) and pairs each real order with what one sent then would buy."""
    head = panel_of(fast(drawn(reply)[0]), FAST_HEAD)
    lede = " ".join(text(p) for p in re.findall(r'<p\b[^>]*\bclass="[^"]*\blr-lede\b[^"]*"[^>]*>(.*?)</p>', head, re.S))
    assert lede, "no lede (a <p class=\"lr-lede\">) in the card's first panel"
    assert re.search(r"2\.4\s?s\b", lede) and re.search(r"(?<![\d.])480(?:\.0)?\s?s\b", lede), lede
    assert "Kalshi" in lede and re.search(r"\bpair", lede, re.I), lede


# ------------------------------------------------------------------ its verdict
@needs_node
@pytest.mark.parametrize("state, label, tone", CHIPS, ids=[s for s, _, _ in CHIPS])
def test_each_verdict_has_its_chip_and_the_servers_words(state, label, tone):
    words = FAST_SAYS[state].format(n=184, target=300)
    base = WAITING_REPLY if state == "waiting" else FAST_REPLY
    c = fast(drawn(with_(base, fastShadow__verdict__state=state, fastShadow__verdict__text=words))[0])
    cls, inner = chip(c)
    assert text(inner).strip() == label, inner
    if tone:
        assert tone in cls, cls
    else:
        assert not cls & {"up", "down", "warn"}, cls
    assert esc(words) in c


@needs_node
def test_an_unknown_verdict_state_is_shown_escaped():
    m = drawn(with_(FAST_REPLY, fastShadow__verdict__state="<b>x</b>"))[0]
    c = fast(m)
    assert "&lt;b&gt;x&lt;/b&gt;" in chip(c)[1] and "<b>x</b>" not in m
    assert esc(FS_TOO_EARLY_TEXT) in c                                          # the rest of the card is still drawn


@needs_node
def test_the_verdict_text_is_shown_escaped():
    early = 'Too early to tell: "fast" <so far> & counting.'
    m = drawn(with_(FAST_REPLY, fastShadow__verdict__text=early))[0]
    assert esc(early) in fast(m) and "<so far>" not in m


# ------------------------------------------------------------------ its head: how far along, since when, how soon after minute 8
@needs_node
def test_it_shows_how_many_orders_are_paired_of_the_target():
    head = text(panel_of(fast(drawn(FAST_REPLY)[0]), FAST_HEAD))
    assert re.search(r"(?<![\d.,])184\s*(?:of|/)\s*300(?![\d,])", head), head
    assert "orders paired on paper" in head, head


@needs_node
def test_it_says_when_the_first_pair_was_made_or_not_yet():
    out = run(replies=[FAST_REPLY, WAITING_REPLY], times=[FS_STARTED])
    (when_, hhmm_), (on, off) = out["times"][0], [h["markup"] for h in out["html"]]
    started = kpis(fast(on)).get("Started")
    assert started is not None, kpis(fast(on))
    assert norm(when_) in started or norm(hhmm_) in started, started
    assert "Not yet" in kpis(fast(off)).get("Started", ""), kpis(fast(off))


@needs_node
def test_it_says_how_soon_after_minute_8_the_marks_book_answered():
    """The median lag, "0.4 s", and 90% within 0.8 s."""
    read = kpis(fast(drawn(FAST_REPLY)[0])).get("Book read")
    assert read is not None, "no \"Book read\" figure on the card"
    assert has_secs(read, 0.37) and "after minute 8" in read, read
    assert re.search(r"90%[^.]*?(?<![\d.])0\.8\s?s\b", read), read


@needs_node
def test_the_books_it_couldnt_read_are_counted_only_when_there_are_some():
    some, none = drawn(FAST_REPLY, with_(FAST_REPLY, fastShadow__unread=0))
    read = kpis(fast(some)).get("Book read", "")
    assert has_num(read, 7), read                                               # 7 unread
    read = kpis(fast(none)).get("Book read", "")
    assert read and not has_num(read, 0) and not re.search(r"\bunread\b|fail|couldn|left out", read, re.I), read


@needs_node
def test_the_caveat_says_this_is_the_best_case_in_one_line():
    """Other traders' orders land 10-30 ms after minute 8, one from this PC about 0.1-0.2 s after it."""
    c = fast(drawn(FAST_REPLY)[0])
    found = re.findall(r'<(\w+)\b[^>]*\bclass="([^"]*\blr-caveat\b[^"]*)"[^>]*>(.*?)</\1>', c, re.S)
    assert len(found) == 1, f"{len(found)} caveats on the card"
    _, cls, inner = found[0]
    assert {"lr-note", "lr-caveat"} <= set(cls.split()), cls
    assert inner.strip().startswith("<b>This is the best case.</b>"), inner
    t = text(inner)
    assert re.search(r"10\s*(?:–|-|to)\s*30\s*ms\b", t), t
    assert re.search(r"0\.1\s*(?:–|-|to)\s*0\.2\s*s\b", t), t


# ------------------------------------------------------------------ real orders against orders at minute 8
def versus(reply=FAST_REPLY):
    return panel_of(fast(drawn(reply)[0]), VERSUS_HEAD)


@needs_node
def test_the_comparison_has_a_real_column_then_an_at_minute_8_one():
    p = versus()
    assert "<table" in p
    head = text(re.search(r"<thead\b.*?</thead>", p, re.S).group(0))
    assert "Real" in head and "At minute 8" in head and head.index("Real") < head.index("At minute 8"), head
    assert re.search(r"2\.4\s?s\b", head) and "on paper" in head, head            # ~2.4 s after minute 8 · on paper


@needs_node
def test_it_shows_the_fill_shares_real_then_at_minute_8_with_their_contracts():
    p = versus()
    row = tr_with(p, "55.0%")
    t = text(row)
    assert share(row, 0.55) and share(row, 0.6732) and t.index("55.0%") < t.index("67.3%"), t
    assert shows(row, "2,750 of 5,000 contracts") and shows(row, "3,366 of 5,000 contracts"), t


@needs_node
@pytest.mark.parametrize("real, at_mark, se, says, rng", [
    (0.55, 0.6732, 0.0821 / 1.96, "+12.3 pts", "(+4.1 to +20.5)"),
    (0.55, 0.4988, 0.0103, "−5.1 pts", "(−7.1 to −3.1)"),                       # a real minus sign, as the tab writes one
], ids=["fills-more", "fills-less"])
def test_the_difference_is_in_signed_points_with_its_95_range(real, at_mark, se, says, rng):
    p = versus(with_(FAST_REPLY, fastShadow__realShare=real, fastShadow__fastShare=at_mark, fastShadow__diff=at_mark - real,
                     fastShadow__diffSe=se))
    row = tr_with(p, "pts")
    assert shows(row, says) and shows(row, rng), text(row)
    assert "(-" not in text(row) and "-5.1" not in text(row)


@needs_node
def test_without_a_standard_error_the_difference_has_no_range():
    row = tr_with(versus(with_(FAST_REPLY, fastShadow__diffSe=None)), "pts")
    assert shows(row, "+12.3 pts"), text(row)
    assert not re.search(r"\(\s*[+−-]?\d+(?:\.\d+)?\s+to\b", text(row)), text(row)


@needs_node
def test_it_shows_the_misses_caught_the_asks_seen_and_the_prices_paid():
    p = versus()
    assert share(p, 616 / 2250), text(p)                                        # 27.4% of the real misses
    for real, at_mark in (("95.1¢", "94.7¢"), ("95.3¢", "94.8¢")):             # the ask it saw, the price paid: real first
        row = tr_with(p, real)
        t = text(row)
        assert at_mark in t and t.index(real) < t.index(at_mark), t


@needs_node
def test_it_shows_the_pnl_and_cents_per_ten_dollars_real_then_on_paper():
    t = text(versus())
    for real, paper in (("+$4.12", "+$9.87"), ("+6.1¢", "+9.4¢"), ("(+0.8 to +11.4)", "(+3.2 to +15.6)")):
        assert real in t and paper in t and t.index(real) < t.index(paper), (real, paper, t)


# ------------------------------------------------------------------ the latest pairs
@needs_node
def test_the_latest_pairs_are_headed_with_their_count():
    """In its heading or, folded, in its fold's header, which shows while the fold is closed."""
    c = fast(drawn(FAST_REPLY)[0])
    heads = headers(c, PAIRS_HEAD)
    assert len(heads) == 1, [t for _, t in h3s(c)]
    assert re.search(r'<span class="lr-n">\s*4\s*</span>', heads[0]), heads[0]


@needs_node
@pytest.mark.parametrize("order", ["as-sent", "reversed"])
def test_the_latest_pairs_keep_the_order_the_server_sent(order):
    rows = FS_ROWS if order == "as-sent" else FS_ROWS[::-1]
    p = panel_of(fast(drawn(with_(FAST_REPLY, fastShadow__rows=rows))[0]), PAIRS_HEAD)
    at = [p.find(r["ticker"]) for r in rows]
    assert -1 not in at and at == sorted(at), at


@needs_node
@pytest.mark.parametrize("i", range(len(FS_ROWS)), ids=[r["ticker"].split("-")[0] for r in FS_ROWS])
def test_each_pair_shows_both_asks_the_limit_what_each_filled_and_how_it_did(i):
    r = FS_ROWS[i]
    out = run(replies=[FAST_REPLY], times=[r["ts"]])
    (when_, hhmm_), m = out["times"][0], out["html"][0]["markup"]
    row = tr_with(panel_of(fast(m), PAIRS_HEAD), r["ticker"])
    t = text(row)
    assert norm(when_) in t or norm(hhmm_) in t, t                              # when it was measured
    assert re.search(rf"\b{r['ticker'][2:5]}\b", t), t                         # its symbol, beside its ticker
    assert re.search(rf"\b{r['side']}\b", t, re.I), t
    assert has_price(row, c_(r["seenReal"])), t                                 # the ask the real order saw
    for k in ("seen", "limit"):                                                 # the ask at minute 8, and its limit
        if r[k] is not None:
            assert has_price(row, c_(r[k])), (k, t)
    for n in (r["asked"], r["filled"], r["extra"]):                             # asked, filled for real, at minute 8
        assert has_num(row, int(n)), (n, t)
    if r["extra"]:
        assert has_price(row, c_(r["avgPrice"])), t                             # what they'd have cost
    else:                                                                       # nothing at minute 8: no price for it
        assert prices(row) <= {c_(r[k]) for k in ("seenReal", "seen", "limit") if r[k] is not None}, t
    assert has_secs(row, r["lag"]), t                                           # how soon the mark's book answered
    assert re.search(rf"\b{r['result']}\b", t, re.I), t


@needs_node
def test_a_pairs_columns_run_time_market_side_asks_limit_asked_filled_price_lag_result():
    row = tr_with(panel_of(fast(drawn(FAST_REPLY)[0]), PAIRS_HEAD), FS_ROWS[0]["ticker"])
    words = cells(row)
    find = lambda f: next((i for i, w in enumerate(words) if f(w)), None)
    at = [find(lambda w: FS_ROWS[0]["ticker"] in w),
          find(lambda w: re.search(r"\byes\b", w, re.I)),
          find(lambda w: has_price(w, "94¢")), find(lambda w: has_price(w, "92¢")), find(lambda w: has_price(w, "93¢")),
          find(lambda w: has_num(w, 23)), find(lambda w: has_num(w, 9)), find(lambda w: has_num(w, 21)),
          find(lambda w: has_price(w, "92.4¢")), find(lambda w: has_secs(w, 0.31)), find(lambda w: re.search(r"\bopen\b", w, re.I))]
    assert None not in at and at == sorted(at) and len(set(at)) == len(at), (at, words)


@needs_node
@pytest.mark.parametrize("rows", [[], None], ids=["empty", "null"])
def test_with_no_pairs_it_says_so_and_draws_no_table(rows):
    p = panel_of(fast(drawn(with_(FAST_REPLY, fastShadow__rows=rows))[0]), PAIRS_HEAD)
    assert "No pairs yet" in text(p) and "<table" not in p, p


# ------------------------------------------------------------------ nothing leaks, nothing breaks
@needs_node
def test_every_server_string_on_the_fast_card_is_escaped():
    """Tickers, sides, results, the verdict and its state come from the server: none may reach the markup raw."""
    ticker = "KX" + HOSTILE + "15M-26OCT111645-45"
    replies = [with_(FAST_REPLY, fastShadow__rows__0__ticker=ticker),
               with_(FAST_REPLY, fastShadow__verdict__text="Too early " + HOSTILE),
               with_(FAST_REPLY, fastShadow__verdict__state=HOSTILE, fastShadow__verdict__text=HOSTILE,
                     fastShadow__rows__0__ticker=ticker, fastShadow__rows__0__side=HOSTILE,
                     fastShadow__rows__0__result=HOSTILE, fastShadow__rows__1__side='yes" onclick="alert(1)')]
    for m in drawn(*replies):
        c = fast(m)
        assert "<script" not in m.lower() and esc(HOSTILE) in c                 # shown, as text
        assert not re.search(r"<[^>]*\sonclick=", m)                            # never an attribute of its own
        assert classes(c) <= TONES | FOLD_CLASSES | {k for k in classes(c) if k.startswith("lr-")}


@needs_node
def test_numbers_sent_as_text_never_reach_the_markup_raw():
    numbers = with_(FAST_REPLY, fastShadow__started=POISON, fastShadow__target=POISON, fastShadow__orders=POISON,
                    fastShadow__unread=POISON, fastShadow__asked=POISON, fastShadow__filled=POISON,
                    fastShadow__realShare=POISON, fastShadow__fastShare=POISON, fastShadow__diff=POISON,
                    fastShadow__diffSe=POISON, fastShadow__caught=POISON, fastShadow__realSeen=POISON,
                    fastShadow__fastAvg=POISON, fastShadow__lag__median=POISON, fastShadow__lag__p90=POISON,
                    fastShadow__pnl__real__pnl=POISON, fastShadow__pnl__paper__perTen=POISON,
                    fastShadow__verdict__orders=POISON, fastShadow__rows__0__seenReal=POISON,
                    fastShadow__rows__0__seen=POISON, fastShadow__rows__0__limit=POISON, fastShadow__rows__0__asked=POISON,
                    fastShadow__rows__0__extra=POISON, fastShadow__rows__0__avgPrice=POISON, fastShadow__rows__0__lag=POISON)
    m = drawn(numbers)[0]
    assert "<img" not in m.lower()
    card(m, "fastshadow")


NULL_ROW = {k: None for k in FS_ROWS[0]}
NULLS = {k: None for k in FAST}
NON_FINITE = with_(FAST_REPLY, fastShadow__started=INF, fastShadow__target=INF, fastShadow__orders=NAN, fastShadow__unread=INF,
                   fastShadow__asked=INF, fastShadow__filled=NAN, fastShadow__extra=NEG_INF, fastShadow__realShare=INF,
                   fastShadow__fastShare=NAN, fastShadow__diff=INF, fastShadow__diffSe=NAN, fastShadow__caught=INF,
                   fastShadow__realSeen=NAN, fastShadow__fastSeen=INF, fastShadow__realAvg=NEG_INF, fastShadow__fastAvg=NAN,
                   fastShadow__lag={"median": NAN, "p90": INF},
                   fastShadow__pnl={"settled": INF, "paper": {"pnl": NAN, "staked": INF, "perTen": INF, "se": NAN},
                                    "real": {"pnl": INF, "staked": NAN, "perTen": NAN, "se": INF}},
                   fastShadow__verdict={"state": "too-early", "text": "Too early to tell.", "orders": NAN, "target": INF},
                   fastShadow__rows=[{**FS_ROWS[0], "ts": INF, "seenReal": NAN, "seen": INF, "limit": NEG_INF, "asked": NAN,
                                      "filled": INF, "extra": NAN, "avgPrice": INF, "lag": NEG_INF, "pnl": NAN},
                                     {**FS_ROWS[1], "extra": INF, "avgPrice": NAN, "filled": NEG_INF}])
ODD = [
    ("recording", FAST_REPLY),
    ("waiting", WAITING_REPLY),
    ("not-yet", NOT_YET),
    ("all-null", {**TODAY, "fastShadow": NULLS}),
    ("all-missing", {**TODAY, "fastShadow": {}}),
    ("non-finite", NON_FINITE),
    ("range-not-finite", with_(FAST_REPLY, fastShadow__diffSe=INF)),
    ("difference-not-finite", with_(FAST_REPLY, fastShadow__diff=NAN)),
    ("no-difference-yet", with_(FAST_REPLY, fastShadow__diff=None, fastShadow__diffSe=None)),
    ("lag-empty", with_(FAST_REPLY, fastShadow__lag={})),
    ("lag-null", with_(FAST_REPLY, fastShadow__lag=None)),
    ("lag-figures-null", with_(FAST_REPLY, fastShadow__lag={"median": None, "p90": None})),
    ("pnl-empty", with_(FAST_REPLY, fastShadow__pnl={})),
    ("pnl-null", with_(FAST_REPLY, fastShadow__pnl=None)),
    ("pnl-real-null", with_(FAST_REPLY, fastShadow__pnl__real=None)),
    ("pnl-paper-empty", with_(FAST_REPLY, fastShadow__pnl__paper={})),
    ("verdict-empty", with_(FAST_REPLY, fastShadow__verdict={})),
    ("verdict-null", with_(FAST_REPLY, fastShadow__verdict=None)),
    ("rows-null", with_(FAST_REPLY, fastShadow__rows=None)),
    ("rows-with-nulls", with_(FAST_REPLY, fastShadow__rows=[NULL_ROW, {"ticker": "KXDOGE15M-26OCT111645-45"},
                                                           {**FS_ROWS[0], "result": None, "side": None, "lag": None}])),
]


@needs_node
@pytest.mark.parametrize("reply", [r for _, r in ODD], ids=[i for i, _ in ODD])
def test_the_fast_card_is_drawn_without_a_missing_number_showing(reply):
    m = drawn(reply)[0]
    c = fast(m)                                                                 # no NaN, undefined, null or Infinity
    assert classes(c) <= TONES | FOLD_CLASSES | {k for k in classes(c) if k.startswith("lr-")}, classes(c)
    for exp in ("shadow", "limitup"):
        card(m, exp)


@needs_node
@pytest.mark.parametrize("value", [THROWS, {"verdict": "x", "lag": [1, 2], "pnl": "y", "rows": "z", "started": "today"}],
                         ids=["throws", "wrong-shapes"])
def test_an_odd_fast_block_never_blanks_the_other_cards(value):
    """A card that throws is replaced by a note (drawCard), so the paper and live cards are drawn just the same."""
    base, m = drawn(TODAY, {**TODAY, "fastShadow": value})
    for exp in ("shadow", "limitup"):
        assert card(m, exp) == card(base, exp), exp
    assert "<b>boom</b>" not in m                                               # an error's words, if any, escaped


@needs_node
@pytest.mark.parametrize("reply", [FAST_REPLY, WAITING_REPLY, NOT_YET], ids=["recording", "waiting", "not-yet"])
def test_the_fast_card_uses_only_the_tabs_own_classes(reply):
    """Every class on it is an .lr- one, a state class the tab already styles (up, down, warn, part, yes, no), or one of
    the shared fold's (fold, fold-h, fold-t, fold-b, chev, fold-m, fold-body)."""
    c = fast(drawn(reply)[0])
    odd = {k for k in classes(c) if not k.startswith("lr-") and k not in TONES | FOLD_CLASSES}
    assert not odd, odd


# ------------------------------------------------------------------ terms
@needs_node
def test_the_terms_gloss_fast_entry():
    m = drawn(FAST_REPLY)[0]
    pairs = {text(t).strip(): text(d) for t, d in re.findall(r"<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>", m, re.S)}
    assert "Fast entry" in pairs, list(pairs)
    d = pairs["Fast entry"]
    assert "minute 8" in d and re.search(r"2\.4\s?s\b", d) and re.search(r"\bpaper\b", d, re.I), d
