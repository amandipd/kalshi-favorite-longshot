"""Live Research, folded: each card, its panels and the Terms fold, and nothing the page said is lost.

Calmer pages that keep every number: each section folds, the headline figures stay in view, long
explanations and secondary tables start folded, and a viewer's choices stick. live_research.js draws its folds with
dashboard.html's shared fold(), so a fold here is a <section class="fold" data-fold-key data-open> holding a header (a
<button> with a chevron and the title, the meta beside it) and a body that a closed fold hides but keeps in the page.
For every reply shape the other Live Research tests use (none yet, a dashboard to restart, an error, not started, too
early, with numbers, the live +1¢ off, a later experiment's key, a card that throws, ...) this checks:

- the folds each page has, by key (lr.shadow, lr.shadow.about, ..., lr.terms), each in fold()'s markup, titled, inside
  its card, and open or closed at first as §3 says; FOLDS lists them with those defaults;
- a card's header holds its title, its state chip and its progress ("412 of 1,000 orders"), so they show while it's
  folded; its verdict and figures stay in the open card outside its "How it's measured" fold, which holds the card's
  explanations and caveat; the +1¢ limit with real money starts closed while it's off, its header saying "Off"; Terms
  start closed; a card that couldn't be drawn shows its note unfolded; a page without the experiments has no folds;
- the page's one Open all / Close all sits in its header with the ledger stamp and reads "Open all" while any fold on
  the page is closed; a stored choice (localStorage "folds") wins over the default, and a stored value that isn't one
  leaves the defaults;
- §2, nothing is removed: every word and number each page held before the folds (folds_baseline_live_research.json,
  captured from the code before the folds were built) is still in it, as many times or more, with the defaults, with
  every fold closed and with every fold open;
- live_research.css (§4): no dashed borders, explanations at most about 72 characters wide, fewer uppercase labels, the
  page's colour tokens only, and no motion without a prefers-reduced-motion rule.

live_research.js runs in node in test_live_research_page.py's harness (the page's helpers and fold helpers cut out of
dashboard.html), with test_fast_shadow_page.py's markers (a card that throws), a stored "folds" choice, and a fixed clock
and locale (Oct 11, 2026, 4:40 PM, New York time), so the baseline reads the same on every run. FOLDS_WRITE_BASELINE=1
writes the baseline from the code as it stands, and refuses once the page folds. The node tests skip themselves without
node.

    python -m pytest tests/test_folds_live_research.py -q
"""

import collections
import functools
import hashlib
import json
import os
import re
import subprocess
from html.parser import HTMLParser

import pytest

from layout import STATIC
from test_fast_shadow_page import FAST, FAST_REPLY, FS_ROWS, NOT_YET, REVIVE, THROWS, WAITING_REPLY
from test_live_research_page import (FULL, HTML, NODE, NOW, ORDERS, RUNNER, TOO_EARLY, WAITING, need_folds, needs_node,
                                     own, page_globals, with_)
from test_shadow_page import BOTH_ON, LIVE_OFF, SH_ROWS, SH_WAITING, TODAY

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "folds_baseline_live_research.json")
TZ = "America/New_York"

# ------------------------------------------------------------------ §3: the folds, their titles and defaults
DEFAULTS = {   # every fold of the page -> open at first
    "lr.shadow": True, "lr.shadow.about": False, "lr.shadow.extra": True, "lr.shadow.pred": False, "lr.shadow.latest": False,
    "lr.fast": True, "lr.fast.about": False, "lr.fast.vs": True, "lr.fast.latest": False,
    "lr.limit": False, "lr.limit.about": False, "lr.limit.fills": False, "lr.limit.extra": True, "lr.limit.pred": False,
    "lr.limit.latest": False,
    "lr.terms": False,
}
ABOUT = "How it's measured"   # every card's .about fold
TITLES = {
    "lr.shadow": "The +1¢ limit, on paper", "lr.shadow.extra": "What the extra cent would have bought",
    "lr.shadow.pred": "Predictions vs paper", "lr.shadow.latest": "Latest paper measurements",
    "lr.fast": "Fast entry, on paper", "lr.fast.vs": "Real orders against orders at minute 8", "lr.fast.latest": "Latest pairs",
    "lr.limit": "The +1¢ limit experiment", "lr.limit.fills": "Fill rates", "lr.limit.extra": "What the extra cent bought",
    "lr.limit.pred": "Predictions vs live", "lr.limit.latest": "Latest experiment orders",
    "lr.terms": "Terms",
}
CARDS = {"lr.shadow": "shadow", "lr.fast": "fastshadow", "lr.limit": "limitup"}   # each card's fold -> its <article data-exp>
CHIPS = {"lr.shadow": {"waiting": "Not recording", "too-early": "Too early to tell"},
         "lr.fast": {"waiting": "Not recording", "too-early": "Too early to tell"},
         "lr.limit": {"waiting": "Not started", "off": "Off", "too-early": "Too early to tell", "helping": "▲ Paying"}}
NOT_RECORDING = {"lr.shadow": "Not recording yet: the bot measures the paper +1¢ from its next restart.",
                 "lr.fast": "Not recording yet: the bot reads the order books at minute 8 exactly from its next restart."}
EXPLAINED = {"lr.shadow": ("counts what a limit", "What paper can't show."),   # each card's lede, then its caveat
             "lr.fast": ("Real orders keep their timing", "This is the best case."),
             "lr.limit": ("immediate-or-cancel buy", None)}
MARKERS = {   # words only that panel holds, on the page with every card and panel
    "lr.shadow.extra": "Fill share with the extra cent", "lr.shadow.pred": "Contracts filled, before",
    "lr.shadow.latest": SH_ROWS[0]["ticker"], "lr.fast.vs": "Misses caught", "lr.fast.latest": FS_ROWS[0]["ticker"],
    "lr.limit.fills": "Contracts asked for", "lr.limit.extra": "only the extra cent bought these",
    "lr.limit.pred": "Live-fills replay", "lr.limit.latest": ORDERS[0]["ticker"], "lr.terms": "Immediate-or-cancel order",
}

# ------------------------------------------------------------------ the reply shapes the other Live Research tests draw
ALL_ON = {**BOTH_ON, "fastShadow": FAST}   # every card with numbers and the live +1¢ on: every fold there is
PAYING_TEXT = "The extra cent is paying: the extra contracts made money, and their 95% range is above zero."
SHAPES = [
    ("none-yet", None),
    ("restart-404", {"httpStatus": 404}),
    ("restart-500", {"httpStatus": 500}),
    ("error", {"error": "no live records yet"}),
    ("unreadable", [1, 2]),
    ("not-started", WAITING),
    ("too-early", TOO_EARLY),
    ("numbers", FULL),
    ("unknown-later-key", with_(FULL, fastEntry={"state": "waiting", "orders": 3, "note": "<b>later</b>"})),
    ("limit-off", TODAY),
    ("paper-waiting", {**TODAY, "shadow": SH_WAITING}),
    ("paper-not-yet", {**LIVE_OFF, "shadowUp": 0.01, "shadow": None}),
    ("both-on", BOTH_ON),
    ("fast", FAST_REPLY),
    ("fast-waiting", WAITING_REPLY),
    ("fast-not-yet", NOT_YET),
    ("all-on", ALL_ON),
    ("paying", with_(ALL_ON, verdict__state="helping", verdict__text=PAYING_TEXT)),
    ("predictions-missing", with_(FAST_REPLY, predictions={"history": None, "live": None})),
    ("card-throws", {**TODAY, "fastShadow": THROWS}),
]
NAMES = [n for n, _ in SHAPES]
REPLIES = dict(SHAPES)


def keys(reply):
    """The folds this reply's page should have (§3): each card's, its "How it's measured", its panels, and Terms."""
    if not isinstance(reply, dict) or reply.get("httpStatus") is not None or reply.get("error") is not None:
        return set()
    out = {"lr.shadow", "lr.shadow.about", "lr.limit", "lr.limit.about", "lr.limit.fills", "lr.terms"}
    if isinstance(reply.get("shadow"), dict):
        out |= {"lr.shadow.extra", "lr.shadow.pred", "lr.shadow.latest"}
    if reply.get("fastShadow") != THROWS:                                       # a card that throws is a note, not a fold
        out |= {"lr.fast", "lr.fast.about"}
        if isinstance(reply.get("fastShadow"), dict):
            out |= {"lr.fast.vs", "lr.fast.latest"}
    if reply["verdict"]["state"] != "off":                                      # off: only its status and the fill rates
        out |= {"lr.limit.extra", "lr.limit.pred", "lr.limit.latest"}
    return out


CARDED = [n for n, r in SHAPES if keys(r)]


def cards(reply):
    """Each card the reply draws: its fold's key -> the block of the reply it shows (None: not recording yet)."""
    blocks = {"lr.shadow": reply.get("shadow"), "lr.fast": reply.get("fastShadow"), "lr.limit": reply}
    return {k: (b if isinstance(b, dict) else None) for k, b in blocks.items() if k in keys(reply)}


def header(k, block):
    """What a card's header says: its chip, and its progress ("412 of 1,000 orders") where the card has one today."""
    if block is None:
        return "Not recording", None
    V = block["verdict"]
    return CHIPS[k][V["state"]], None if V["state"] == "off" else f"{V['orders']:,} of {V['target']:,} orders"


def verdict(k, block):
    return NOT_RECORDING[k] if block is None else block["verdict"]["text"]


def figures(k, block):
    """Labels from a card's strip of figures, as it has them today."""
    if block is None:
        return []                                                               # not recording yet: no figures
    if k == "lr.limit":
        return ["Live limit", "Each fill recorded"] if block["verdict"]["state"] == "off" else ["Started", "Limit", "Each fill recorded"]
    return ["Started", "Book read"]


def explained(k, block):
    lede, caveat = EXPLAINED[k]
    return [lede] + ([caveat] if caveat and block is not None else [])


def counts(reply):
    """Each "Latest ..." fold on the page -> how many rows it lists."""
    found, c = keys(reply), cards(reply) if keys(reply) else {}
    rows = {"lr.shadow.latest": (c.get("lr.shadow") or {}).get("rows"), "lr.fast.latest": (c.get("lr.fast") or {}).get("rows"),
            "lr.limit.latest": reply.get("orders") if found else None}
    return {k: len(v or []) for k, v in rows.items() if k in found}


# ------------------------------------------------------------------ drawing it in node
CLOCK = ("const __RealDate = Date;\n"   # a fixed now and locale: when() says "4:38 PM" today and "Oct 9, 1:40 PM" before
         "globalThis.Date = class extends __RealDate {\n"
         f"  constructor(...a) {{ if (a.length) super(...a); else super({NOW * 1000:.0f}); }}\n"
         f"  static now() {{ return {NOW * 1000:.0f}; }}\n"
         '  toLocaleTimeString(l, o) { return super.toLocaleTimeString("en-US", o); }\n'
         '  toLocaleDateString(l, o) { return super.toLocaleDateString("en-US", o); }\n'
         "};\n")


def render(replies, storage=None):
    """liveResearchHtml(reply) of each reply, in node, with what localStorage holds (storage) and a fixed clock."""
    if not NODE:
        pytest.skip("node isn't installed")
    js, parse = page_globals(), "const __in = JSON.parse(__input);"
    assert parse in js, "test_live_research_page.py's page_globals() no longer parses its input that way: update render()"
    payload = {"pageJs": js.replace(parse, REVIVE + "const __in = JSON.parse(__input, __revive);\n" + CLOCK, 1),
               "file": os.path.join(STATIC, "live_research.js"), "replies": list(replies), "page": "account", "data": None,
               "fetches": [], "steps": [], "times": [], "lrHidden": False, "storage": storage or {}}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, "TZ": TZ})
    assert r.returncode == 0, r.stderr
    return [h["markup"] for h in json.loads(r.stdout)["html"]]


def choose(choices):
    """localStorage holding these fold choices."""
    return {"folds": json.dumps(choices)}


def every(open_):
    """Every fold of the page open (or closed): §3's and any other the page draws."""
    return choose({k: open_ for k in set(DEFAULTS) | {key(f) for m in pages("defaults").values() for f in folds_of(m)}})


@functools.lru_cache(maxsize=None)
def pages(state):
    """Every shape's page (name -> markup) with nothing stored ("defaults"), every fold "closed", or every one "open"."""
    storage = None if state == "defaults" else every(state == "open")
    return dict(zip(NAMES, render([r for _, r in SHAPES], storage)))


# ------------------------------------------------------------------ reading the markup
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class El:
    """An element: its tag, attributes, parent, and children (elements and strings of text)."""
    def __init__(self, tag, attrs, up):
        self.tag, self.attrs, self.up, self.kids = tag, dict(attrs), up, []

    @property
    def cls(self):
        return set((self.attrs.get("class") or "").split())


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.at = El("#root", (), None)

    def handle_starttag(self, tag, attrs):
        el = El(tag, attrs, self.at)
        self.at.kids.append(el)
        if tag not in VOID:
            self.at = el

    def handle_startendtag(self, tag, attrs):
        self.at.kids.append(El(tag, attrs, self.at))

    def handle_endtag(self, tag):
        el = self.at
        while el.up is not None and el.tag != tag:
            el = el.up
        if el.up is not None:
            self.at = el.up

    def handle_data(self, s):
        self.at.kids.append(s)


@functools.lru_cache(maxsize=None)
def dom(markup):
    t = Tree()
    t.feed(markup)
    t.close()
    return t.root


def elements(el):
    """Every element under el, in the page's order."""
    for k in el.kids:
        if isinstance(k, El):
            yield k
            yield from elements(k)


def children(el):
    return [k for k in el.kids if isinstance(k, El)]


def ancestors(el):
    while el.up is not None:
        el = el.up
        yield el


def strings(el, skip=lambda e: False):
    """Every text under el, entities decoded, leaving out the elements skip() picks."""
    for k in el.kids:
        if isinstance(k, str):
            yield k
        elif not skip(k):
            yield from strings(k, skip)


def words(el):
    return " ".join(" ".join(strings(el)).split())


def holders(el, phrase):
    """The innermost elements under el whose words hold phrase."""
    hits = [e for e in elements(el) if phrase in words(e)]
    return [e for e in hits if not any(phrase in words(k) for k in children(e))]


def folds_of(markup):
    return [e for e in elements(dom(markup)) if e.tag == "section" and "data-fold-key" in e.attrs]


def key(f):
    return f.attrs["data-fold-key"]


def fold_by(markup, k):
    found = [f for f in folds_of(markup) if key(f) == k]
    assert len(found) == 1, f"{len(found)} folds keyed {k}; the page's are {[key(f) for f in folds_of(markup)]}"
    return found[0]


def head(f):
    return children(f)[0]


def body(f):
    return children(f)[1]


def title(f):
    """A fold's title: its button's own words, less its chevron and anything nested (a count)."""
    button = children(children(head(f))[0])[0]
    return " ".join(" ".join(k for k in button.kids if isinstance(k, str)).split()).replace("’", "'")


def check(f):
    """A fold in fold()'s markup, its parts agreeing on whether it's open: True when it's open."""
    k, is_open = key(f), f.attrs.get("data-open")
    assert "fold" in f.cls and is_open in ("true", "false"), f"{k}: {f.attrs}"
    parts = children(f)
    assert [(p.tag, "fold-h" in p.cls, "fold-body" in p.cls) for p in parts] == [("div", True, False), ("div", False, True)], \
        f"{k}: a fold holds its header (div.fold-h), then its body (div.fold-body): {[(p.tag, p.attrs.get('class')) for p in parts]}"
    h, b = parts
    inside = children(h)
    assert inside and inside[0].tag == "h2" and "fold-t" in inside[0].cls, f'{k}: its header starts with <h2 class="fold-t">'
    assert len(inside) <= 2 and all(x.tag == "span" and "fold-m" in x.cls for x in inside[1:]), \
        f"{k}: after its heading its header holds at most its meta, a span.fold-m"
    button = children(inside[0])
    assert len(button) == 1 and button[0].tag == "button" and "fold-b" in button[0].cls, f"{k}: its heading holds one button.fold-b"
    a = button[0].attrs
    assert (a.get("type"), a.get("data-fold"), a.get("aria-expanded"), a.get("aria-controls")) == ("button", k, is_open, "fold-" + k), \
        f"{k}: its button {a}"
    chev = children(button[0])
    assert chev and chev[0].tag == "i" and "chev" in chev[0].cls and chev[0].attrs.get("aria-hidden") == "true", \
        f"{k}: its button starts with its chevron"
    assert b.attrs.get("id") == "fold-" + k and ("hidden" in b.attrs) == (is_open == "false"), \
        f"{k}: its body is #fold-{k}, hidden only while it's closed: {b.attrs}"
    return is_open == "true"


def where(el):
    """The fold nearest around el, and the part of it el is in: (key, "head" or "body"), or (None, None)."""
    part, up = el, el.up
    while up is not None:
        if up.tag == "section" and "data-fold-key" in up.attrs:
            return key(up), "body" if "fold-body" in part.cls else "head"
        part, up = up, up.up
    return None, None


def folds_buttons(markup):
    return [e for e in elements(dom(markup)) if e.tag == "button" and "data-folds" in e.attrs]


# ------------------------------------------------------------------ dashboard.html's fold helpers, and FOLDS
FOLDS_RUNNER = """
const vm = require("vm"), fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ console, __input: "{}" });
vm.runInContext(input.pageJs, ctx, { filename: "dashboard.html (page globals)" });
process.stdout.write(vm.runInContext("JSON.stringify(FOLDS)", ctx));
"""


@needs_node
def test_dashboard_html_has_the_shared_fold_helpers_live_research_draws_with():
    """FOLDS, folds, foldOpen(), fold() and foldsButton(), cut out of the page by name."""
    need_folds()


@needs_node
def test_folds_lists_every_live_research_fold_with_its_default():
    """§3's table, as FOLDS has it (key -> open at first): the +1¢ limit with real money is closed (it's off for now)."""
    need_folds()
    r = subprocess.run([NODE, "-e", FOLDS_RUNNER], input=json.dumps({"pageJs": page_globals()}), capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    folds = json.loads(r.stdout)
    assert {k: bool(v) for k, v in folds.items() if k.startswith("lr.")} == DEFAULTS


# ------------------------------------------------------------------ §3: which sections fold, and how they start
@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_the_page_has_the_folds_section_3_lists_each_in_folds_markup(shape):
    need_folds()
    m = pages("defaults")[shape]
    found = [key(f) for f in folds_of(m)]
    assert len(found) == len(set(found)), f"a fold key is used twice: {found}"
    assert set(found) == keys(REPLIES[shape]), f"extra {set(found) - keys(REPLIES[shape])}, missing {keys(REPLIES[shape]) - set(found)}"
    for f in folds_of(m):
        check(f)


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_each_fold_starts_open_or_closed_as_section_3_says(shape):
    """Headline figures open, long explanations and secondary tables closed. §3 has the live +1¢ card closed while
    it's off ("FOLDS default false"); once it's on, the page may open it, so that case is left to the page."""
    need_folds()
    off = REPLIES[shape]["verdict"]["state"] == "off"
    for f in folds_of(pages("defaults")[shape]):
        k = key(f)
        if k != "lr.limit" or off:
            assert check(f) == DEFAULTS[k], f"{k} starts {'open' if check(f) else 'closed'}"


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_each_fold_is_titled_and_sits_in_its_card(shape):
    """A card is one fold in its <article class="lr-card" data-exp>; its "How it's measured" and its panels are folds
    in its body; Terms is a fold of its own after the cards."""
    need_folds()
    for f in folds_of(pages("defaults")[shape]):
        k = key(f)
        card = k.rsplit(".", 1)[0] if k.count(".") == 2 else None
        assert title(f) == (ABOUT if k.endswith(".about") else TITLES[k]), f"{k} is titled {title(f)!r}"
        assert where(f) == ((card, "body") if card else (None, None)), f"{k} sits in {where(f)}"
        if k in CARDS:
            article = next((a for a in ancestors(f) if a.tag == "article"), None)
            assert article is not None and "lr-card" in article.cls and article.attrs.get("data-exp") == CARDS[k], \
                f'{k} isn\'t in its <article class="lr-card" data-exp="{CARDS[k]}">'


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_a_cards_header_shows_its_title_chip_and_progress_while_its_folded(shape):
    """With every fold closed: the title, the state chip ("Too early to tell", "Off", "▲ Paying") and the progress
    ("412 of 1,000 orders") are in the card's header, outside its hidden body."""
    need_folds()
    m = pages("closed")[shape]
    for k, block in cards(REPLIES[shape]).items():
        f = fold_by(m, k)
        assert not check(f) and title(f) == TITLES[k], (k, title(f))
        chip, progress = header(k, block)
        chips = [words(e) for e in elements(f) if "lr-chip" in e.cls and where(e) == (k, "head")]
        assert chip in chips, f"{k}'s header has the chips {chips}, not {chip!r}"
        if progress:
            assert re.search(rf"(?<![\d.,]){re.escape(progress)}\b", words(head(f))), f"{k}'s header: {words(head(f))!r}"


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_a_cards_verdict_and_figures_stay_in_the_open_card_outside_how_its_measured(shape):
    """The verdict sentence and the strip of figures sit in the card's own body, in no fold of their own."""
    need_folds()
    m = pages("defaults")[shape]
    for k, block in cards(REPLIES[shape]).items():
        f = fold_by(m, k)
        said = verdict(k, block)
        assert (k, "body") in [where(e) for e in holders(f, said)], f"{k}'s verdict {said!r} isn't in its body, outside its folds"
        for label in figures(k, block):
            spots = [where(e) for e in elements(f) if words(e) == label]
            assert (k, "body") in spots, f"{k}'s figure {label!r} sits in {spots}, not in its body outside its folds"


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_a_cards_explanations_and_caveat_fold_into_how_its_measured(shape):
    need_folds()
    m = pages("defaults")[shape]
    for k, block in cards(REPLIES[shape]).items():
        f = fold_by(m, k)
        for phrase in explained(k, block):
            spots = {where(e) for e in holders(f, phrase)}
            assert spots == {(k + ".about", "body")}, f"{phrase!r} sits in {spots}, not in {k}.about"


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_each_latest_panel_says_its_count_in_its_header(shape):
    """The key number of a list, its count, shows while the list is folded."""
    need_folds()
    m = pages("closed")[shape]
    for k, n in counts(REPLIES[shape]).items():
        said = words(head(fold_by(m, k)))
        assert re.search(rf"(?<![\d.,]){n}(?![\d,]|\.\d)", said), f"{k}'s header doesn't say its {n} rows: {said!r}"


@needs_node
@pytest.mark.parametrize("k", sorted(MARKERS))
def test_each_panel_fold_holds_its_own_panel(k):
    need_folds()
    m = pages("defaults")["all-on"]
    assert k in [where(e)[0] for e in holders(dom(m), MARKERS[k])], f"{MARKERS[k]!r} isn't in {k}"


@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_a_closed_fold_keeps_its_body_in_the_page(shape):
    """Folded is a hidden body, still there: nothing is drawn only once it's opened."""
    need_folds()
    for f in folds_of(pages("closed")[shape]):
        assert not check(f) and words(body(f)), f"{key(f)}'s body is empty while it's closed"


@needs_node
def test_the_live_limit_card_starts_closed_while_its_off_with_off_in_its_header():
    need_folds()
    f = fold_by(pages("defaults")["limit-off"], "lr.limit")
    assert not check(f) and title(f) == TITLES["lr.limit"]
    assert "Off" in [words(e) for e in elements(head(f)) if "lr-chip" in e.cls]
    assert "Every order so far" in words(body(f))                               # its fill rates are in it, hidden


@needs_node
def test_terms_are_one_fold_closed_at_first():
    need_folds()
    m = pages("defaults")["all-on"]
    f = fold_by(m, "lr.terms")
    assert not check(f) and title(f) == "Terms" and where(f) == (None, None)
    assert all(where(e)[0] == "lr.terms" for e in elements(dom(m)) if e.tag in ("dt", "dd"))


@needs_node
def test_a_card_that_couldnt_be_drawn_shows_its_note_unfolded():
    """drawCard's note in place of a card that throws: in no fold, and not hidden."""
    m = pages("defaults")["card-throws"]
    notes = holders(dom(m), "This experiment's card couldn't be drawn.")
    assert notes, "no note for the card that throws"
    for e in notes:
        assert where(e) == (None, None), f"the note sits in the fold {where(e)}"
        assert not any("hidden" in a.attrs for a in [e, *ancestors(e)]), "the note is hidden"
        assert "<b>boom</b>" in words(e.up)                                      # the error's words, as text


@needs_node
@pytest.mark.parametrize("shape, says", [("none-yet", "Loading the live experiments"), ("restart-404", "Restart the dashboard"),
                                         ("restart-500", "Restart the dashboard"), ("error", "No live research to show."),
                                         ("unreadable", "An answer this tab can't read.")])
def test_a_page_without_the_experiments_has_no_folds_and_shows_its_note(shape, says):
    m = pages("defaults")[shape]
    assert not folds_of(m), [key(f) for f in folds_of(m)]
    found = holders(dom(m), says)
    assert found and not any("hidden" in a.attrs for e in found for a in [e, *ancestors(e)]), says


# ------------------------------------------------------------------ the page's Open all / Close all
@needs_node
@pytest.mark.parametrize("shape", CARDED)
def test_the_pages_open_all_sits_in_its_header_with_the_ledger_stamp(shape):
    need_folds()
    m = pages("defaults")[shape]
    found = folds_buttons(m)
    assert len(found) == 1, f"{len(found)} Open all / Close all buttons on the page"
    top = next(e for e in elements(dom(m)) if e.tag == "header")
    assert top in ancestors(found[0]), "the Open all / Close all isn't in the page's header"
    assert "Live Research" in words(top) and "ledger" in words(top), words(top)


OPEN_ALL = [   # (shape, the folds stored closed, every other one stored open; None: nothing stored), what it says
    ("limit-off", None, "open"),                                                # at first some folds are closed
    ("limit-off", (), "close"),
    ("all-on", ("lr.terms",), "open"),
    ("fast", ("lr.fast",), "open"),
    ("limit-off", ("lr.limit.pred", "lr.limit.latest"), "close"),               # closed, but not on this page: the live +1¢ is off
]


@needs_node
@pytest.mark.parametrize("shape, closed, says", OPEN_ALL, ids=["defaults", "all-open", "one-closed", "card-closed", "unshown-closed"])
def test_open_all_reads_open_all_while_any_fold_on_the_page_is_closed(shape, closed, says):
    need_folds()
    storage = None if closed is None else choose({k: k not in closed for k in json.loads(every(True)["folds"])})
    found = folds_buttons(render([REPLIES[shape]], storage)[0])
    assert len(found) == 1, f"{len(found)} Open all / Close all buttons on the page"
    assert (found[0].attrs.get("data-folds"), words(found[0])) == (says, {"open": "Open all", "close": "Close all"}[says])


# ------------------------------------------------------------------ the viewer's choices
@needs_node
@pytest.mark.parametrize("shape, choices", [
    ("limit-off", {"lr.limit": True}),                                          # the viewer opened the live +1¢ while it's off
    ("limit-off", {"lr.shadow": False, "lr.shadow.about": True, "lr.terms": True}),
    ("all-on", {"lr.fast.vs": False, "lr.fast.latest": True, "lr.limit.pred": True, "lr.limit": True}),
], ids=["open-the-off-card", "paper-card", "fast-and-live"])
def test_a_stored_choice_wins_over_the_default(shape, choices):
    need_folds()
    m = render([REPLIES[shape]], choose(choices))[0]
    off = REPLIES[shape]["verdict"]["state"] == "off"
    for f in folds_of(m):
        k = key(f)
        if k in choices:
            assert check(f) == choices[k], f"{k} ignores its stored choice"
        elif k != "lr.limit" or off:
            assert check(f) == DEFAULTS[k], f"{k} isn't at its default"


@needs_node
@pytest.mark.parametrize("raw", ["{not json", "[true, false]", '"lr.terms"', '{"lr.terms": "yes", "lr.shadow": 0, "lr.limit": null}'],
                         ids=["not-json", "a-list", "a-string", "not-booleans"])
def test_a_stored_value_that_isnt_a_choice_leaves_the_defaults(raw):
    need_folds()
    m = render([TODAY], {"folds": raw})[0]
    assert {key(f): check(f) for f in folds_of(m)} == {k: DEFAULTS[k] for k in keys(TODAY)}


# ------------------------------------------------------------------ §2: nothing is removed
CONTROLS = re.compile(r"Expand all|Collapse all|Open all|Close all|Show all [\d,]+|Show fewer|Show less|Chart options|Hide|Show")


def control(el):
    """A button whose words are one of the control labels §2 lets change or go."""
    return el.tag == "button" and CONTROLS.fullmatch(words(el)) is not None


def tokens(markup):
    """What a page says, as §2 counts it: the words of every text in it, folded or not, hidden or not, entities decoded,
    split at whitespace, less the control labels. Each text counts on its own, as each element's text does."""
    return collections.Counter(w for s in strings(dom(markup), control) for w in s.split())


def md5(name):
    with open(os.path.join(STATIC, name), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def write_golden():
    """The baseline: every shape's reply and the words its page says, drawn by the code as it stands. Only before the
    folds: once the page folds, it's no longer the page §2 compares against."""
    drawn = render([r for _, r in SHAPES])
    folded = [n for n, m in zip(NAMES, drawn) if folds_of(m) or folds_buttons(m)]
    if folded:
        pytest.fail(f"the page folds already ({folded}): the baseline is the page from before the folds, so it can't be written now")
    shapes = {n: {"reply": r, "tokens": dict(sorted(tokens(m).items()))} for (n, r), m in zip(SHAPES, drawn)}
    top = {"about": "Live Research before the folds: for each reply shape, the reply and the words its "
                    "page says (token -> count), drawn in node by test_folds_live_research.py with nothing stored, now "
                    "fixed at Oct 11, 2026 4:40 PM and TZ America/New_York. Written once, before any fold was built.",
           "made from": {f: md5(f) for f in ("live_research.js", "dashboard.html")}, "now": NOW, "tz": TZ}
    text = json.dumps(top, ensure_ascii=False, indent=1)[:-2] + ',\n "shapes": {\n' + ",\n".join(
        f'  {json.dumps(n)}: {{\n   "reply": {json.dumps(s["reply"], ensure_ascii=False)},\n'
        f'   "tokens": {json.dumps(s["tokens"], ensure_ascii=False)}\n  }}' for n, s in shapes.items()) + "\n }\n}\n"
    assert json.loads(text) == {**top, "shapes": shapes}
    with open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


@functools.lru_cache(maxsize=None)
def golden():
    if os.environ.get("FOLDS_WRITE_BASELINE") == "1":
        write_golden()
    if not os.path.exists(GOLDEN):
        pytest.fail(f"{os.path.basename(GOLDEN)} is missing: it's written once, from the page before the folds")
    with open(GOLDEN, encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=None)
def golden_pages(state):
    """The baseline's replies drawn by the code as it stands now: name -> markup."""
    shapes = golden()["shapes"]
    storage = None if state == "defaults" else every(state == "open")
    return dict(zip(shapes, render([s["reply"] for s in shapes.values()], storage)))


@needs_node
def test_the_baseline_covers_every_reply_shape():
    assert list(golden()["shapes"]) == NAMES


@needs_node
@pytest.mark.parametrize("state", ["defaults", "closed", "open"])
@pytest.mark.parametrize("shape", NAMES)
def test_nothing_the_page_said_is_removed(shape, state):
    """Every word the page held before the folds is still in it, as many times or more, and every number (a word with a
    digit in it) too: with the defaults, with every fold closed, and with every fold open."""
    before = collections.Counter(golden()["shapes"][shape]["tokens"])
    m = golden_pages(state)[shape]
    now = tokens(m)
    if "· every 2 s" in m:   # the one change of wording since (the faster polling): the header's "every 5 s" is "every 2 s"
        before -= collections.Counter({"5": 1})
    broke = [words(e.up) for e in holders(dom(m), "card couldn't be drawn.")]
    assert len(broke) <= before["drawn."], f"a card couldn't be drawn: {broke}"
    numbers = {t: n - now[t] for t, n in before.items() if re.search(r"\d", t) and now[t] < n}
    assert not numbers, f"numbers gone from the page ({state}), with how many times each went: {numbers}"
    gone = before - now
    assert not gone, f"words gone from the page ({state}), with how many times each went: {dict(gone)}"


# ------------------------------------------------------------------ §4: live_research.css
def css():
    return re.sub(r"/\*.*?\*/", "", own("live_research.css"), flags=re.S)


def test_no_panel_has_a_dashed_border():
    """One panel style: the paper card's dashed rule goes."""
    assert "dashed" not in css()


def test_explanations_run_at_most_about_72_characters_wide():
    widths = [float(w) for w in re.findall(r"max-width:\s*([\d.]+)ch\b", css())]
    assert widths and max(widths) <= 75, widths


def test_fewer_labels_are_set_in_uppercase():
    """Today four rules set labels in capitals (panel titles, figure labels, table heads, yes/no); a plain label reads fine."""
    assert len(re.findall(r"text-transform:\s*uppercase", css())) < 4


def test_it_paints_only_with_the_pages_colour_tokens():
    """So the light and dark themes (and test_light_theme.py's contrast checks) cover every colour on the tab."""
    s = css()
    defined = set(re.findall(r"--([\w-]+)\s*:", HTML + s))
    used = set(re.findall(r"var\(--([\w-]+)", s))
    assert used <= defined, sorted(used - defined)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|color-mix)\(", s), "a colour of its own"
    assert not re.search(r":[^;{}]*\b(?:white|black|red|green|blue|gr[ae]y|silver|orange|yellow|purple|pink)\b", s), "a named colour"


def test_any_motion_respects_prefers_reduced_motion():
    s = css()
    if re.search(r"\b(?:transition|animation)[\w-]*\s*:", s):
        assert "prefers-reduced-motion" in s
