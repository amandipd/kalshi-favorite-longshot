"""How the dashboard looks: the polish pass's rules, read straight from its two stylesheets.

The polish pass made the pages more minimal and clean, and wrote that down as a short list of rules: one type scale and two weights, uppercase for two roles only, one face for numbers, no box inside a box, colour
only where it means something, one spacing scale, one left edge, one table style, one radius scale, a readable line
length, two cues on the current tab, phone-sized tap targets, and dark mode keeping its hairlines. These tests check
rules 1 to 13 and 15 by reading the CSS of both stylesheets the page loads, in the order it loads them:
dashboard.html's <style>, then live_research.css, then latency.css (the Historical Research tab's sheet left with the
tab on Oct 15; the Latency tab's arrived the same day).
Rules 9 and 14, and the muted "—" of rule 8, need the page's markup: those are checked on the Live tab drawn for real
in node, with test_folds_live.py's stand-in browser and its fixed data (they skip without node).

Nothing here changes text: the tests read CSS and the markup's classes and order, never the words.

How the CSS is read (css_rules): comments are dropped (a /* inside a quoted string is left alone); the text is walked
brace by brace, so an @media or @supports block is read rule by rule with its condition remembered (nested blocks
join their conditions with "and"), and @keyframes / @font-face blocks are skipped (they hold no selectors). Each rule
keeps its sheet, its media condition, its selector list split at the commas that sit outside (), [] and quotes (so
`:is(a, b)` stays whole), and its declarations split at the semicolons outside () and quotes, each as (property,
value) with whitespace collapsed and "!important" dropped. A `font:` shorthand is read token by token (font_parts):
the size is the first length, var() or calc() before the family (which always comes last), the line-height after a
"/" is ignored, and a weight is a 3-digit number or bold/bolder/lighter before the size; `font: 600 11px/1.3
var(--sans)` reads as weight 600, size 11px. A selector is split into compounds at its combinators (space, >, + and
~ outside brackets); its subject is the last compound, whose element type and classes say what it styles. Values in px
(also inside calc() or a shorthand) are read with px_values; var(--sp-N), var(--fs-N) and var(--r-*) are resolved
from the spec's own token table, so a check never depends on the tokens being there yet.

Inline styles that the page scripts write (style="..." in dashboard.html's script and live_research.js)
are read as rules too, for the checks on values (sizes, weights, spacing, radii); a declaration built from a ${...}
placeholder is skipped.

Where the spec is loose, this file pins one reading and says so beside the constant or the test.

    python -m pytest -q -p no:cacheprovider tests/test_look.py
"""

import copy
import os
import re
from collections import namedtuple

import pytest

from kalshi_bot.web import dashboard

HERE = os.path.dirname(os.path.abspath(dashboard.PAGE))
HTML = open(dashboard.PAGE, encoding="utf-8").read()


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


STYLE = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)

# ------------------------------------------------------------------ what the spec allows, in one place
# The tokens: defined once, in a dashboard.html :root rule, for both themes.
TOKENS = {"--fs-1": "11px", "--fs-2": "12.5px", "--fs-3": "13.5px", "--fs-4": "15px", "--fs-5": "20px", "--fs-6": "26px",
          "--fs-7": "60px",
          "--sp-1": "4px", "--sp-2": "8px", "--sp-3": "12px", "--sp-4": "16px", "--sp-5": "24px", "--sp-6": "32px",
          "--sp-7": "48px",
          "--r-1": "6px", "--r-2": "10px", "--r-pill": "999px"}

# Rule 1: the type scale, and the two weights.
FONT_SIZES = {11, 12.5, 13.5, 15, 20, 26, 60}
HERO = "hv"                 # the hero figure: 48px on phones (a max-width <= 560px query) is its one extra size,
                            # and -0.01em its one extra letter-spacing
SAME_SIZE = {"inherit", "100%", "1em", "0"}   # pinned: not a new size. The parent's size, or 0, which hides the words
                                              # (the navbar status shows its dot alone on a phone)
WEIGHTS = {"400", "600", "normal", "inherit"}

# Rule 2: uppercase for two roles only (and the one-word state chips), at 0.06em.
UPPER_SPACING = "0.06em"
KPI_LABEL = re.compile(r"(?:[a-z0-9]+-)*k")   # pinned reading of ".k, .lr-k, .sc labels and the like": a
                                              # subject with a class named k or <prefix>-k (.k, .lr-k, ...)
CHIPS = {"chip", "lr-chip", "pill", "bd-in",   # the spec's list
         "lr-side",   # pinned: Live Research's YES/NO side badge, the same thing as .pill
         "tagtxt"}    # pinned: the chart's START / 1H AGO tag (grouped with the chips)
NEVER_UPPER = [".nav-b", ".grp button", ".fold-t", ".fold-b", ".lr-ph h3", ".mg h3"]

# Rule 3: numbers. Table number cells are sans with tabular figures; --mono only where the text is code-like.
NUMBER_TABLES = {".bd-t": ("bd-t",), "#orders": ("#orders",), ".lr-t": ("lr-t", "lr-orders")}
NUMBER_CELL_CLASSES = {"lr-num", "num", "r"}
MONO_OK = ["code", ".lr-stamp", ".lr-tk", ".cv text", ".axis text", ".axis", ".lr-axis"]
                            # tickers (.lr-tk), code, the ledger stamp, chart axis text (the account chart's ticks are
                            # `.cv text`, the fill-rate chart's `.fr .axis`, an SVG's inline class="axis"; Live
                            # Research's .lr-axis)

# Rule 4: no box in a box.
KPI_STRIPS = {"lr-kpis"}
KPI_ITEMS = {"lr-kpi"}
NO_STRIPE = {"lr-lead", "lr-paper", "lr-card"}

# Rule 6: the spacing scale.
SPACES = {0, 1, 2, 4, 8, 12, 16, 24, 32, 48}
SPACE_PROP = re.compile(r"(?:margin|padding)(?:-[a-z-]+)?|(?:row-|column-|grid-|grid-row-|grid-column-)?gap")
WRAP_GAP = 32
FOLDED_APART = 8
# where each page's top-level folds stack: (page, the container they sit in, the sheet holding its folded-row rule).
# The Backtest tab (Oct 28) has no folds, so it is not here; its sheet is still read, through RULES below.
STACKS = [("Live", ".wrap", "dashboard.html"), ("Live Research", "#liveresearch", "live_research.css"), ("Latency", "#latency", "latency.css")]

# Rule 7: one left edge. Each header: the selectors that style it (base first), and the fold button inside it, whose
# own left padding adds to the header's (the chevron, the header's first mark, then starts 16px in).
EDGE = 16
BETWEEN = 12
HEADERS = {"a fold's header": ([".fold-h"], ".fold-b"),
           "a Live Research panel header": ([".lr-ph"], None)}

# Rule 8: one table style.
ROW_PAD = 8
TABLE_TEXT = 13.5

# Rule 10: phones.
PHONE = 560
PHONE_WIDTHS = (560, 480, 400, 360)
TAP = 44
TAP_TARGETS = [".nav-b", ".grp button", ".ghost", ".folds-b", ".icon-btn", ".fold-h"]   # the last: the fold header
# each wrapper -> the selectors that may reach its tables' first column (pinned: the wrapper's class, or its table's;
# for .table-wrap, a rule naming no class at all, which reaches every table)
STICKY = {".table-wrap": ["table-wrap", None], ".bd-wrap": ["bd-wrap", "bd-t"], ".lr-tw": ["lr-tw", "lr-t"]}

# Rule 11: radii. Pinned: 0 (a square corner, e.g. a fold flush inside a card) isn't a radius, so it's allowed.
RADII = {0, 6, 10, 999}

# Rule 12: explanation paragraphs and the Terms definitions (pinned list: the prose under Live Research's cards and its
# Terms, and Live's How it trades; dashboard.html's .lede is left out, no markup uses it). A selector no rule styles any
# more is skipped; any max-width in ch over 72 fails.
MEASURE = 72
EXPLANATIONS = [".lr-title p", ".lr-verdict", ".lr-lede", ".lr-note", ".lr-dl dd", ".mg ul"]

# Rule 15: panels.
PANELS = {"fold", "lr-card", "lr-exp"}

# ------------------------------------------------------------------ reading CSS
Rule = namedtuple("Rule", "sheet media selector parts decls")


def uncomment(css):
    """css without its /* comments */; a comment marker inside a quoted string is left alone."""
    out, i, n = [], 0, len(css)
    while i < n:
        c = css[i]
        if c in "\"'":
            j = css.find(c, i + 1)
            j = n if j < 0 else j + 1
            out.append(css[i:j])
            i = j
        elif css.startswith("/*", i):
            j = css.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def split_top(text, seps):
    """text split at each character of `seps` that sits outside (), [] and quotes; empty pieces dropped."""
    parts, cur, depth, quote = [], [], 0, None
    for c in text:
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif depth == 0 and c in seps:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(c)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def words(value):
    return split_top(value, " \t\n")


def block_end(css, start):
    """The index of the } that closes the { at css[start]."""
    depth, quote = 0, None
    for j in range(start, len(css)):
        c = css[j]
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
    raise AssertionError(f"an unclosed {{ in the CSS near {css[start:start + 60]!r}")


def declarations(body):
    out = []
    for d in split_top(body, ";"):
        if ":" not in d:
            continue
        prop, value = d.split(":", 1)
        value = re.sub(r"\s*!important\s*$", "", " ".join(value.split()), flags=re.I)
        out.append((prop.strip().lower(), value))
    return out


def css_rules(css, sheet, media=""):
    """Every style rule of `css`, in source order, those inside @media/@supports included (with their condition)."""
    css = uncomment(css)
    rules, i = [], 0
    while True:
        j = css.find("{", i)
        if j < 0:
            assert not css[i:].strip().strip("}").strip(), f"{sheet}: CSS after the last rule: {css[i:i + 80]!r}"
            return rules
        prelude = " ".join(css[i:j].split())
        k = block_end(css, j)
        inner = css[j + 1:k]
        if prelude.startswith(("@media", "@supports")):
            cond = prelude.split(None, 1)[1] if " " in prelude else ""
            rules += css_rules(inner, sheet, f"{media} and {cond}" if media else cond)
        elif not prelude.startswith("@"):                   # @keyframes, @font-face: no selectors in them
            assert "{" not in re.sub(r"\"[^\"]*\"|'[^']*'", "", inner), \
                f"{sheet}: a nested rule inside {prelude!r} (this reader doesn't read CSS nesting)"
            rules.append(Rule(sheet, media, prelude, split_top(prelude, ","), declarations(inner)))
        i = k + 1


def inline_rules(src, name):
    """The static style="..." attributes a script writes, each as a rule named by its tag as written (so a failure
    shows where it is); a ${...} declaration is left out."""
    out = []
    for m in re.finditer(r'style="([^"]*)"', src):
        decls = [(p, v) for p, v in declarations(m.group(1)) if "${" not in p + v]
        if decls:
            tag = " ".join(src[src.rfind("<", 0, m.start()):m.end()].split())
            out.append(Rule(f"{name} (inline style)", "", tag if len(tag) < 200 else "…" + tag[-200:], [], decls))
    return out


RULES = (css_rules(STYLE, "dashboard.html") + css_rules(read("live_research.css"), "live_research.css")
         + css_rules(read("latency.css"), "latency.css") + css_rules(read("backtest.css"), "backtest.css"))
INLINE = (inline_rules(SCRIPT, "dashboard.html") + inline_rules(read("live_research.js"), "live_research.js")
          + inline_rules(read("latency.js"), "latency.js") + inline_rules(read("backtest.js"), "backtest.js"))


def at(r):
    """Where a rule is: sheet [media] selector."""
    return f"{r.sheet}{f' [{r.media}]' if r.media else ''} {r.selector}"


def where(r, prop=None, value=None):
    """How an offender is named in a failure: sheet [media] selector { prop: value } (all its declarations without prop)."""
    body = f"{prop}: {value}" if prop else "; ".join(f"{p}: {v}" for p, v in r.decls)
    return f"{at(r)} {{ {body} }}"


def report(offenders, what):
    offenders = list(dict.fromkeys(offenders))          # a rule listed once, however many of its selectors matched
    return f"{what} ({len(offenders)}):\n  " + "\n  ".join(offenders)


# ------------------------------------------------------------------ reading selectors
def norm(sel):
    """A selector with its combinators spaced one way and attribute values double-quoted."""
    sel = re.sub(r"\s*([>+~])\s*(?![^\[]*\])", r" \1 ", sel)
    sel = re.sub(r"\[([\w-]+)=([^\"'\]]+)\]", r'[\1="\2"]', sel)
    sel = sel.replace("'", '"')
    return " ".join(sel.split())


def compounds(sel):
    return split_top(sel, " >+~\t\n")


def subject(sel):
    return compounds(sel)[-1]


def bare(compound):
    """A compound without its pseudo-classes, pseudo-elements and attribute tests: what element it is."""
    c = re.sub(r"::?[\w-]+(?:\((?:[^()]|\([^()]*\))*\))?", "", compound)
    return re.sub(r"\[[^\]]*\]", "", c)


def tag_of(compound):
    m = re.match(r"[a-zA-Z][\w-]*|\*", compound)
    return m.group(0).lower() if m else ""


def classes_of(compound):
    return set(re.findall(r"\.([\w-]+)", bare(compound)))


def ids_of(compound):
    return set(re.findall(r"#([\w-]+)", bare(compound)))


def ends(sel, target, states=False):
    """Whether selector `sel` styles `target`: its last compounds are target's (a context before them is fine).
    states=True also counts the target in a state (:hover, [aria-pressed="true"], ::after)."""
    a = [bare(c) if states else c for c in compounds(norm(sel))]
    b = compounds(norm(target))
    return len(a) >= len(b) and a[-len(b):] == b


def max_width(media):
    m = re.findall(r"max-width:\s*(\d+(?:\.\d+)?)px", media)
    return min(float(x) for x in m) if m else None


def applies_at(media, width):
    """Whether a rule's media condition holds at a viewport `width` (width None: a desktop, i.e. no max-width)."""
    if width is None:
        return max_width(media) is None
    for kind, n in re.findall(r"(min|max)-width:\s*(\d+(?:\.\d+)?)px", media):
        if (kind == "min" and width < float(n)) or (kind == "max" and width > float(n)):
            return False
    return True


def cascade(chain, width=None):
    """The declarations that reach an element styled by the selectors in `chain` (base first, then more specific),
    as rules in source order whose selector list holds one of them exactly and whose media holds at `width`."""
    chain = [norm(s) for s in chain]
    out = []
    for sel in chain:                           # a more specific selector wins whatever its place in the source
        for r in RULES:
            if applies_at(r.media, width) and any(norm(p) == sel for p in r.parts):
                out += r.decls
    return out


def last(decls, *props):
    hit = None
    for p, v in decls:
        if p in props:
            hit = v
    return hit


# ------------------------------------------------------------------ reading values
def var_px(name):
    v = TOKENS.get("--" + name)
    return float(v[:-2]) if v and v.endswith("px") else None


def px(value):
    """A length in px: "16px", "0", "var(--sp-4)", "-8px", "calc(-1 * var(--sp-6))"; None for anything else (auto, %,
    em, a var() that isn't a spec token)."""
    if value is None:
        return None
    v = value.strip()
    if v in ("0", "0px", "-0"):
        return 0.0
    expr = re.sub(r"var\(--([\w-]+)\)", lambda m: str(var_px(m.group(1))), v)
    expr = re.sub(r"(\d)px", r"\1", expr)
    expr = re.sub(r"^calc\((.*)\)$", r"\1", expr)
    if "None" in expr or not re.fullmatch(r"[\d.\s+\-*/()]+", expr):
        return None
    try:
        return float(eval(expr, {"__builtins__": {}}))
    except Exception:
        return None


def px_values(value):
    """Every px length in a value, literal or a spec token, with its sign: "0 -6px 0 var(--sp-1)" -> [-6, 4]."""
    out = [float(x) for x in re.findall(r"(-?\d*\.?\d+)px", value)]
    for neg, name in re.findall(r"(-?)var\(--([\w-]+)\)", value):
        n = var_px(name)
        if n is not None:
            out.append(-n if neg else n)
    return out


def unknown_tokens(value, prefix, names):
    """var(--<prefix>...) references to tokens the spec doesn't define."""
    return [m for m in re.findall(rf"var\(--({prefix}[\w-]*)\)", value) if m not in names]


SIZE = re.compile(r"-?\d*\.?\d+(?:px|em|rem|%|pt|ch|vw|vh|vmin|vmax)|0|var\(--[\w-]+\)|calc\(.*\)"
                  r"|(?:xx?-|xxx-)?(?:small|large)|medium|smaller|larger")
WEIGHT = re.compile(r"\d{3}|bold|bolder|lighter")


def font_parts(value):
    """(weight, size) of a `font:` shorthand: "600 11px/1.3 var(--sans)" -> ("600", "11px"); "12.5px var(--mono)" ->
    (None, "12.5px"). A lone keyword (inherit) -> ("inherit", "inherit"). Size "?" when no size can be found."""
    toks = words(value)
    if len(toks) == 1 and toks[0] in ("inherit", "initial", "unset", "revert"):
        return toks[0], toks[0]
    for i, t in enumerate(toks[:-1]):                  # the family always comes last
        head = split_top(t, "/")[0]
        if SIZE.fullmatch(head):
            weight = next((w for w in toks[:i] if WEIGHT.fullmatch(w)), None)
            return weight, head
    return None, "?"


def fonts(r):
    """[(prop, value, weight, size)] for the rule's font, font-size and font-weight declarations."""
    out = []
    for p, v in r.decls:
        if p == "font":
            w, s = font_parts(v)
            out.append((p, v, w, s))
        elif p == "font-size":
            out.append((p, v, None, v))
        elif p == "font-weight":
            out.append((p, v, v, None))
    return out


def weight_of(decls):
    """The weight these declarations leave: font-weight, or a font shorthand's (normal when it names none)."""
    w = None
    for p, v in decls:
        if p == "font":
            fw, _ = font_parts(v)
            w = fw or "400"
        elif p == "font-weight":
            w = v
    return {"normal": "400", "bold": "700"}.get(w, w)


def sides(decls, prop="padding"):
    """{top, right, bottom, left: value} that `prop` (padding or margin) and its longhands set, in order."""
    out = {}
    for p, v in decls:
        if p == prop:
            w = words(v)
            t = w[0]
            r = w[1] if len(w) > 1 else t
            b = w[2] if len(w) > 2 else t
            out.update(top=t, right=r, bottom=b, left=w[3] if len(w) > 3 else r)
        elif p.startswith(prop + "-"):
            side = p[len(prop) + 1:]
            if side in ("top", "right", "bottom", "left"):
                out[side] = v
            elif side in ("inline", "block"):
                w = words(v)
                a, b = w[0], (w[1] if len(w) > 1 else w[0])
                out.update(left=a, right=b) if side == "inline" else out.update(top=a, bottom=b)
            elif side in ("inline-start", "inline-end", "block-start", "block-end"):
                out[{"inline-start": "left", "inline-end": "right", "block-start": "top", "block-end": "bottom"}[side]] = v
    return out


def zero_border(value):
    return bool(re.fullmatch(r"(?:0(?:px)?|none|transparent)(?:\s+(?:0(?:px)?|none|transparent|var\([\w-]+\)))*", value))


def no_fill(value):
    return value in ("none", "transparent", "inherit", "unset", "initial", "0 0")


def muted_classes():
    """Classes that set text in --muted by themselves (a rule whose whole selector is that one class)."""
    out = set()
    for r in RULES:
        if last(r.decls, "color") == "var(--muted)":
            out |= {m.group(1) for p in r.parts for m in [re.fullmatch(r"\.([\w-]+)", norm(p))] if m}
    return out


# ------------------------------------------------------------------ the reader itself
def test_the_reader_reads_selectors_media_and_shorthands():
    css = """/* a { color: red } */ .a, :is(.b, .c) > td:first-child { font: 600 11px/1.3 var(--sans); margin: 0 -6px }
             @media (max-width: 560px) { .d { content: "{;}"; padding: 8px 12px 4px } }
             @keyframes k { from { opacity: 0 } }"""
    rules = css_rules(css, "t")
    assert [(r.parts, r.media) for r in rules] == [([".a", ":is(.b, .c) > td:first-child"], ""), ([".d"], "(max-width: 560px)")]
    assert font_parts("600 11px/1.3 var(--sans)") == ("600", "11px")
    assert font_parts("12.5px var(--mono)") == (None, "12.5px")
    assert font_parts("600 var(--fs-1)/1.3 var(--sans)") == ("600", "var(--fs-1)")
    assert tag_of(subject(rules[0].parts[1])) == "td" and px_values("0 -6px") == [-6.0]
    assert sides(rules[1].decls) == {"top": "8px", "right": "12px", "bottom": "4px", "left": "12px"}
    assert px("calc(-1 * var(--sp-6))") == -32 and ends(".chart-tools .grp button[aria-pressed=true]", ".grp button", states=True)
    assert RULES and len({r.sheet for r in RULES}) == 4, "every stylesheet was read"   # the page's, and the three tabs'


# ------------------------------------------------------------------ the tokens
def test_the_tokens_are_defined_once_in_dashboard_htmls_root():
    defined = {}
    for r in RULES:
        for p, v in r.decls:
            if p in TOKENS:
                defined.setdefault(p, []).append((r, v))
    missing = sorted(set(TOKENS) - set(defined))
    assert not missing, f"tokens not defined anywhere: {', '.join(missing)} (the polish pass's tokens)"
    wrong = [f"{p}: {v} in {where(r)[:80]}" for p, hits in defined.items() for r, v in hits
             if v != TOKENS[p] or r.sheet != "dashboard.html" or r.media or norm(r.selector) != ":root"]
    twice = [p for p, hits in defined.items() if len(hits) > 1]
    assert not wrong and not twice, report(wrong + [f"{p} defined {len(defined[p])} times" for p in twice],
                                           "each token is defined once, in dashboard.html's :root, "
                                           "with the spec's value")


def test_every_token_reference_names_a_spec_token():
    names = {k[2:] for k in TOKENS}
    bad = [where(r, p, v) for r in RULES + INLINE for p, v in r.decls
           if unknown_tokens(v, "fs-", names) or unknown_tokens(v, "sp-", names) or unknown_tokens(v, "r-", names)]
    assert not bad, report(bad, "var(--fs-*), var(--sp-*) and var(--r-*) that the spec doesn't define")


# ------------------------------------------------------------------ 1. the type scale
def size_ok(size, r):
    if size in SAME_SIZE or re.fullmatch(r"var\(--fs-[1-7]\)", size):
        return True
    m = re.fullmatch(r"(\d*\.?\d+)px", size)
    if not m:
        return False
    n = float(m.group(1))
    if n in FONT_SIZES:
        return True
    phone = max_width(r.media) is not None and max_width(r.media) <= PHONE
    return n == 48 and phone and r.parts and all(HERO in classes_of(subject(p)) for p in r.parts)


def test_every_font_size_is_on_the_scale():
    bad = [where(r, p, v) for r in RULES + INLINE for p, v, w, s in fonts(r) if s is not None and not size_ok(s, r)]
    assert not bad, report(bad, f"font sizes off the scale {sorted(FONT_SIZES)} px (48px only for .{HERO} on phones), "
                                "var(--fs-N); SVG chart text and inline styles included")


def test_only_two_weights():
    bad = [where(r, p, v) for r in RULES + INLINE for p, v, w, s in fonts(r)
           if w is not None and w not in WEIGHTS and not (p == "font" and w == s)]
    assert not bad, report(bad, f"weights other than {sorted(WEIGHTS)}")


# ------------------------------------------------------------------ 2. uppercase for two roles; letter-spacing
def role(sel):
    """'header' (a table column header), 'label' (a KPI/figure label), 'chip' (a one-word state chip) or None."""
    s = subject(norm(sel))
    if tag_of(s) == "th":
        return "header"
    cls = classes_of(s)
    if any(KPI_LABEL.fullmatch(c) for c in cls):
        return "label"
    return "chip" if cls & CHIPS else None


def uppercase(r):
    return last(r.decls, "text-transform") == "uppercase"


def test_uppercase_only_on_column_headers_kpi_labels_and_state_chips():
    bad = [f"{where(r, 'text-transform', 'uppercase')}  <- {p}" for r in RULES if uppercase(r)
           for p in r.parts if not role(p)]
    assert not bad, report(bad, "uppercase on something that isn't a th, a KPI label (.k, .lr-k, ...) or a state chip")


@pytest.mark.parametrize("target", NEVER_UPPER)
def test_never_uppercase(target):
    bad = [where(r, "text-transform", "uppercase") for r in RULES if uppercase(r)
           and any(ends(p, target, states=True) for p in r.parts)]
    assert not bad, report(bad, f"{target} is set in capitals (sentence case: drop the text-transform)")


def test_uppercase_rules_space_their_letters_by_0_06em():
    bad = [where(r, "letter-spacing", last(r.decls, "letter-spacing")) for r in RULES if uppercase(r)
           and last(r.decls, "letter-spacing") != UPPER_SPACING]
    assert not bad, report(bad, f"uppercase rules without letter-spacing: {UPPER_SPACING}")


def test_every_other_letter_spacing_is_zero():
    bad = []
    for r in RULES + INLINE:
        for p, v in r.decls:
            if p != "letter-spacing" or v in ("0", "0em", "0px", "normal", "inherit"):
                continue
            if v == UPPER_SPACING and r.parts and all(role(s) for s in r.parts):
                continue
            if v == "-0.01em" and r.parts and all(HERO in classes_of(subject(s)) for s in r.parts):
                continue
            bad.append(where(r, p, v))
    assert not bad, report(bad, f"letter-spacing other than 0 ({UPPER_SPACING} on the uppercase roles, -0.01em on .{HERO})")


# ------------------------------------------------------------------ 3. numbers
def uses_mono(r):
    return any(p in ("font", "font-family") and "var(--mono)" in v for p, v in r.decls)


def test_body_sets_tabular_figures():
    decls = cascade(["body"])
    assert "tabular-nums" in (last(decls, "font-variant-numeric") or ""), \
        "body doesn't set font-variant-numeric: tabular-nums (every digit the same width, so columns line up)"


def number_cell(sel):
    """Whether a selector styles a number cell of the board, the orders or a Live Research table."""
    cs = compounds(norm(sel))
    s = cs[-1]
    if classes_of(s) & {"lr-num"}:
        return True
    if tag_of(s) != "td":
        return False
    names = {c for comp in cs for c in classes_of(comp)} | {"#" + i for comp in cs for i in ids_of(comp)}
    return any(names & set(prefixes) for prefixes in NUMBER_TABLES.values())


def test_table_number_cells_are_not_monospace():
    bad = [f"{where(r)}  <- {p}" for r in RULES if uses_mono(r) for p in r.parts if number_cell(p)]
    assert not bad, report(bad, "table number cells set in var(--mono) (sans with tabular figures instead)")


def test_mono_only_on_tickers_code_the_ledger_stamp_and_chart_axis_text():
    bad = [f"{where(r)}  <- {p}" for r in RULES if uses_mono(r) for p in r.parts
           if not any(ends(p, ok) for ok in MONO_OK)]
    bad += [where(r) for r in INLINE if uses_mono(r) and 'class="axis"' not in r.selector]
    assert not bad, report(bad, f"var(--mono) outside {MONO_OK}")


# ------------------------------------------------------------------ 4. no box in a box
def subjects_with(classes):
    for r in RULES:
        for p in r.parts:
            if classes_of(subject(norm(p))) & classes:
                yield r, p


def test_kpi_strips_have_no_box_no_fill_and_at_most_a_top_hairline():
    bad = []
    for r, p in subjects_with(KPI_STRIPS | KPI_ITEMS):
        item = bool(classes_of(subject(norm(p))) & KPI_ITEMS)
        for prop, v in r.decls:
            if prop in ("background", "background-color") and not no_fill(v):
                bad.append(where(r, prop, v))
            elif prop == "box-shadow" and v != "none":
                bad.append(where(r, prop, v))
            elif prop.startswith("border") and "radius" not in prop and not zero_border(v) \
                    and (item or prop not in ("border-top", "border-top-width", "border-top-style", "border-top-color")):
                bad.append(where(r, prop, v))
    assert not bad, report(bad, "KPI strips (.lr-kpis) and their items boxed, filled or ruled (one top "
                                "hairline on the strip is all they may have)")


def test_no_accent_stripe_on_live_research_cards_and_leads():
    bad = [where(r, prop, v) for r, p in subjects_with(NO_STRIPE) for prop, v in r.decls
           if (prop.startswith("border-left") or prop.startswith("border-inline-start")) and not zero_border(v)
           or prop == "box-shadow" and "inset" in v and not re.match(r"inset\s+0(?:px)?\s", v)]
    assert not bad, report(bad, "a left stripe on .lr-lead / .lr-paper / .lr-card")


def test_the_caveat_has_no_wash_or_stripe_and_keeps_its_warn_ink_lead_in():
    bad = [where(r, prop, v) for r, p in subjects_with({"lr-caveat"}) for prop, v in r.decls
           if prop in ("background", "background-color") and not no_fill(v)
           or prop.startswith("border") and "radius" not in prop and not zero_border(v)
           or prop == "box-shadow" and v != "none"]
    assert not bad, report(bad, ".lr-caveat has a wash, a stripe or a box")
    lead = [r for r in RULES for p in r.parts if norm(p).endswith(".lr-caveat b")]
    assert any(last(r.decls, "color") == "var(--warn-ink)" for r in lead), \
        ".lr-caveat b (\"What paper can't show.\") is no longer --warn-ink: the warning must still carry a word as well as a colour"


def test_nothing_is_dashed():
    bad = [where(r, p, v) for r in RULES + INLINE for p, v in r.decls if re.search(r"\bdashed\b", v)]
    assert not bad, report(bad, "dashed borders")


# ------------------------------------------------------------------ 5. colour by meaning
def test_the_next_entry_timer_is_not_orange():
    bad = [where(r) for r in RULES for p in r.parts
           if ".timer" in p and tag_of(subject(norm(p))) == "b" and "down" not in classes_of(subject(norm(p)))
           and any("--warn" in v for _, v in r.decls)]
    assert not bad, report(bad, "the Next entry timer (.timer b) uses --warn (it keeps .down for its alarm)")


def test_the_progress_bar_is_neutral():
    bad = [where(r) for r in RULES for p in r.parts
           if ".lr-bar" in p and tag_of(subject(norm(p))) == "i"
           and any(re.search(r"--(?:brand|up|warn)", v) for _, v in r.decls)]
    assert not bad, report(bad, "the Live Research progress bar (.lr-bar i) uses --brand / --up / --warn")


# ------------------------------------------------------------------ 6. spacing
def test_every_margin_padding_and_gap_is_on_the_spacing_scale():
    bad = [where(r, p, v) for r in RULES + INLINE for p, v in r.decls
           if SPACE_PROP.fullmatch(p) and any(abs(n) not in SPACES for n in px_values(v))]
    assert not bad, report(bad, f"margin / padding / gap in px off the scale {sorted(SPACES)} (or var(--sp-N))")


def row_gap(decls):
    v = last(decls, "gap", "row-gap", "grid-gap", "grid-row-gap")
    for p, val in decls:                        # the row gap is a gap shorthand's first value, or row-gap's
        if p in ("gap", "grid-gap"):
            v = words(val)[0]
        elif p in ("row-gap", "grid-row-gap"):
            v = val
    return px(v) if v is not None else 0.0


def test_the_pages_sections_are_32px_apart():
    assert row_gap(cascade([".wrap"])) == WRAP_GAP, \
        f".wrap's gap is {last(cascade(['.wrap']), 'gap')}, not {WRAP_GAP}px (var(--sp-6)): more space between sections than inside them"


def folded_rows(sel, container, own_sheet):
    """Whether `sel` is a page's "folded fold right after a folded fold" rule: two [data-open="false"] tests joined by
    +, and either scoped to the page's container (.wrap > ...; in any sheet) or, in the page's own sheet, starting at
    the fold itself (so a rule for folds nested inside a card doesn't count)."""
    n = norm(sel)
    if n.count('[data-open="false"]') < 2 or " + " not in n:
        return False
    first = compounds(n)[0]
    return first == container or (own_sheet and '[data-open="false"]' in first)


@pytest.mark.parametrize("page,container,sheet", STACKS, ids=[s[0] for s in STACKS])
def test_folded_folds_stack_8px_apart(page, container, sheet):
    gap = row_gap(cascade([container]))
    pulls = [px(last(r.decls, "margin-top", "margin-block-start") or (sides(r.decls, "margin").get("top")))
             for r in RULES if not r.media for p in r.parts if folded_rows(p, container, r.sheet == sheet)]
    apart = sorted({gap + (m or 0) for m in pulls}) or [gap]
    assert apart == [FOLDED_APART], (f"{page}: two folded folds in a row sit {apart} px apart ({container} gap {gap}px, "
                                     f"folded-row margin-top {pulls or 'none'}), not {FOLDED_APART}px")


# ------------------------------------------------------------------ 7. one left edge
def styled(chain):
    return any(any(norm(p) == norm(s) for p in r.parts) for r in RULES for s in chain)


@pytest.mark.parametrize("name", HEADERS)
def test_headers_start_16px_in(name):
    chain, button = HEADERS[name]
    if not styled(chain[-1:]):
        pytest.skip(f"no rule styles {chain[-1]}")
    pad = sides(cascade(chain))
    left = (px(pad.get("left")) or 0) + ((px(sides(cascade([button])).get("left")) or 0) if button else 0)
    right = px(pad.get("right")) or 0
    assert (left, right) == (EDGE, EDGE), (f"{name} ({chain[-1]}{' and its ' + button if button else ''}) starts "
                                          f"{left:g}px in and ends {right:g}px from the right edge, not {EDGE}px")


def test_headers_in_other_contexts_start_16px_in_too():
    named = {norm(s) for chain, _ in HEADERS.values() for s in chain}
    bad = []
    for name, (chain, button) in HEADERS.items():
        for r in RULES:
            if not applies_at(r.media, None):
                continue
            for p in r.parts:
                if norm(p) in named or not ends(p, chain[-1]) or not {"left", "right"} & set(sides(r.decls)):
                    continue
                pad = sides(cascade(chain + [p]))
                left = (px(pad.get("left")) or 0) + ((px(sides(cascade([button])).get("left")) or 0) if button else 0)
                if (left, px(pad.get("right")) or 0) != (EDGE, EDGE):
                    bad.append(f"{where(r)}  <- {name} at {left:g}px / {px(pad.get('right')) or 0:g}px")
    assert not bad, report(bad, f"headers styled in a context that moves them off the {EDGE}px edge")


def cell_rules(prefixes):
    """(rule, selector, 'first'|'last'|'between') for every desktop rule styling a cell of a table named by prefixes."""
    for r in RULES:
        if not applies_at(r.media, None):
            continue
        for p in r.parts:
            cs = compounds(norm(p))
            names = {c for comp in cs[:-1] for c in classes_of(comp)} | {"#" + i for comp in cs[:-1] for i in ids_of(comp)}
            names |= classes_of(cs[0]) | {"#" + i for i in ids_of(cs[0])}
            if not names & set(prefixes):
                continue
            s = cs[-1]
            cell = tag_of(s) in ("td", "th") or classes_of(s) & NUMBER_CELL_CLASSES \
                or (tag_of(s) in ("", "*") and len(cs) > 1 and tag_of(cs[-2]) == "tr")
            if not cell:
                continue
            pos = "first" if re.search(r":first-(?:child|of-type)", s) else "last" if re.search(r":last-(?:child|of-type)", s) else "between"
            yield r, p, pos


@pytest.mark.parametrize("table", NUMBER_TABLES)
def test_table_cells_pad_16px_at_the_edges_and_12px_between(table):
    prefixes = NUMBER_TABLES[table]
    bad, have = [], set()
    for r, p, pos in cell_rules(prefixes):
        pad = sides(r.decls)
        for side in ("left", "right"):
            if side not in pad:
                continue
            want = EDGE if (pos, side) in (("first", "left"), ("last", "right")) else BETWEEN
            if px(pad[side]) != want:
                bad.append(f"{at(r)}  <- {pos} cells' {side} padding {pad[side]}, not {want}px")
            elif prefixes[0] in {c for comp in compounds(norm(p)) for c in classes_of(comp) | {'#' + i for i in ids_of(comp)}}:
                have.add((pos, side))
    edges = {("first", "left"), ("last", "right")}
    missing = sorted((edges | {("between", "left"), ("between", "right")}) - have)
    bad += [f"no {table} rule gives its {a} cells {s} padding {EDGE if (a, s) in edges else BETWEEN}px" for a, s in missing]
    assert not bad, report(bad, f"{table}: first and last cells pad {EDGE}px at the side, cells between {BETWEEN}px")


# ------------------------------------------------------------------ 8. one table style
def test_no_column_header_has_a_fill():
    # pinned: var(--surface), the panel's own colour, isn't a fill (a sticky header or first column needs it to cover
    # what scrolls under it); a row header in tbody and a hover wash aren't column headers
    bad = [where(r, prop, v) for r in RULES for p in r.parts
           if tag_of(subject(norm(p))) == "th" and "tbody" not in p and ":hover" not in p
           for prop, v in r.decls if prop in ("background", "background-color") and not no_fill(v) and v != "var(--surface)"]
    assert not bad, report(bad, "column headers with a background fill")


@pytest.mark.parametrize("table", NUMBER_TABLES)
def test_rows_are_one_line_at_8px_padding_and_13_5px_text(table):
    bad = []
    for r, p, _ in cell_rules(NUMBER_TABLES[table]):
        pad = sides(r.decls)
        bad += [f"{at(r)}  <- {side} padding {pad[side]}" for side in ("top", "bottom")
                if side in pad and px(pad[side]) != ROW_PAD]
        if tag_of(subject(norm(p))) != "th" or "tbody" in p:            # a row header is a cell; a column header is 11px
            bad += [f"{at(r)}  <- cell text {s}" for prop, v, w, s in fonts(r)
                    if s is not None and s not in ("inherit", f"{TABLE_TEXT:g}px", "var(--fs-3)")]
    for r in RULES:          # the table's own text size
        for p in r.parts:
            s = subject(norm(p))
            if classes_of(s) & set(NUMBER_TABLES[table]) and tag_of(s) in ("", "table") and len(compounds(norm(p))) == 1:
                bad += [where(r, prop, v) for prop, v, w, sz in fonts(r)
                        if sz is not None and sz not in ("inherit", f"{TABLE_TEXT:g}px", "var(--fs-3)")]
    assert not bad, report(bad, f"{table}: rows ~36px need {ROW_PAD}px vertical cell padding and {TABLE_TEXT:g}px text")


def test_every_table_sets_its_text_at_13_5px():
    # the Live tab's Orders and Details tables take the plain table / td rules
    bad = [where(r, prop, v) for r in RULES for p in r.parts if norm(p) in ("table", "td")
           for prop, v, w, s in fonts(r) if s is not None and s not in ("inherit", f"{TABLE_TEXT:g}px", "var(--fs-3)")]
    assert not bad, report(bad, f"table text that isn't {TABLE_TEXT:g}px")


def test_a_muted_unit_class_exists():
    hits = [r for r in RULES for p in r.parts if ends(p, ".u") and last(r.decls, "color") == "var(--muted)"]
    assert hits, 'no .u rule setting color: var(--muted) (for the units, as in 99<span class="u">&cent;</span>)'


# ------------------------------------------------------------------ the Live tab drawn (rules 8, 9, 14)
def live_page(**state):
    """The Live tab as test_folds_live.py's stand-in browser draws it from its fixed data, with `state` changed."""
    from test_folds_live import golden, run
    g = copy.deepcopy(golden())
    g["state"].update(state)
    return run(inputs=g)[0]


def section_of(el):
    """The id of the nearest element around `el` that has one (#board, #orders, #more ...)."""
    while el is not None and not el.attrs.get("id"):
        el = el.parent
    return el.attrs["id"] if el is not None else "?"


def test_the_empty_cell_dash_is_muted():
    # pinned: checked on the Live tab drawn from test_folds_live.py's fixed data (the board's market with no price yet,
    # the orders' results, the Details tables); a cell holding just "—" must carry, on itself or on the element around
    # the dash, a class whose own rule sets color: var(--muted) (.muted, or a new one)
    page = live_page()
    muted = muted_classes()
    cells = [e for e in page.live() if e.tag in ("td", "th") and e.text() == "—"]
    assert cells, "the fixed data drew no table cell holding just a dash (the board's market with no price has some)"
    bad = [f"<{c.tag} class=\"{c.attrs.get('class', '')}\"> holding a lone dash, in #{section_of(c)}" for c in cells
           if not any(set(e.attrs.get("class", "").split()) & muted for e in [c, *c.els()] if e.text() == "—")]
    assert not bad, report(bad, "empty cells whose dash isn't in a class that sets color: var(--muted)")


def test_details_rows_put_their_chevron_before_the_title():
    page = live_page()
    rows = [e for e in page.live() if e.tag == "summary" and e.parent.has_class("acc")]
    assert rows, "no Details rows (.acc) on the Live tab"
    bad = []
    for s in rows:
        kids = [k.attrs.get("class", k.tag) for k in s.children()]
        chev = next((i for i, k in enumerate(s.children()) if k.has_class("chev")), None)
        title = next((i for i, k in enumerate(s.children()) if k.has_class("t")), None)
        if chev is None or title is None or chev > title:
            bad.append(f'{s.parent.attrs.get("data-sec")}: {kids}')
    assert not bad, report(bad, "Details rows whose chevron isn't on the left, before the title, in the markup")


@pytest.mark.parametrize("sel", [".fold-t", ".fold-b"])
def test_the_fold_button_stretches_across_its_header(sel):
    flex = last(cascade([sel]), "flex", "flex-grow") or "0"
    grow = {"auto": 1.0, "none": 0.0}.get(words(flex)[0], px(words(flex)[0]))
    assert grow and grow >= 1, \
        f"{sel} doesn't grow across its header (flex: {flex}): the whole header row should be the click target"


def test_the_open_all_buttons_sit_at_the_right():
    # pinned loosely: Live's sits in a right-aligned row above its folds; Live Research's header spreads its title and
    # its tools apart
    assert HTML.index('id="liveFolds"') < HTML.index('id="positions"'), "Live's Open all is no longer above its folds"
    assert last(cascade([".live-folds"]), "justify-content") == "flex-end", ".live-folds isn't right-aligned"
    assert last(cascade([".lr-head"]), "justify-content") == "space-between", "Live Research's header doesn't push its tools right"


def test_an_empty_positions_list_is_one_muted_line():
    page = live_page(openBets=[])
    body = page.fold("live.positions").body
    kids = body.children()
    text = body.text()
    assert "No open bets" in text and "New ones are placed at minute 8 of each 15-minute window." in text, \
        f"the empty Positions text changed: {text!r}"
    assert not [e for e in body.els() if e.tag in ("svg", "img")], "the empty Positions still draws an icon"
    assert len(kids) == 1 and not [e for e in kids[0].els() if e.tag in ("div", "p", "ul", "table", "br")], \
        f"the empty Positions isn't one line: {[k.tag + '.' + k.attrs.get('class', '') for k in body.els()]}"
    line = kids[0]
    cls = set(line.attrs.get("class", "").split())
    assert cls & muted_classes() or [r for r in RULES for p in r.parts if classes_of(subject(norm(p))) & cls
                                     and last(r.decls, "color") == "var(--muted)"], \
        f"the empty Positions line ({line.tag}.{'.'.join(sorted(cls))}) isn't muted"
    tall = [where(r, side, v) for r in RULES for p in r.parts if classes_of(subject(norm(p))) and classes_of(subject(norm(p))) <= cls
            and tag_of(subject(norm(p))) in ("", line.tag) for side, v in sides(r.decls).items()
            if side in ("top", "bottom") and (px(v) or 0) > 12]
    assert not tall, report(tall, "the empty Positions line is padded taller than a row")


# ------------------------------------------------------------------ 10. phones
def tap_height(target, width):
    """(height in px, hidden?) of `target` at a viewport `width`: max(height, min-height) from its own rules."""
    decls = [d for r in RULES if applies_at(r.media, width) and any(norm(p) == norm(target) for p in r.parts) for d in r.decls]
    if last(decls, "display") == "none":
        return None, True
    return max(px(last(decls, "height")) or 0, px(last(decls, "min-height", "block-size")) or 0), False


@pytest.mark.parametrize("target", TAP_TARGETS)
def test_phone_tap_targets_are_44px_tall(target):
    short = []
    for w in PHONE_WIDTHS:
        h, hidden = tap_height(target, w)
        if not hidden and h < TAP:
            short.append(f"{h:g}px at {w}px wide")
    assert not short, f"{target} on a phone is {', '.join(short)}: under {TAP}px (set min-height in the max-width: {PHONE}px query)"


@pytest.mark.parametrize("wrap", STICKY)
def test_phone_tables_keep_their_first_column_in_view(wrap):
    names = STICKY[wrap]
    decls = []
    for r in RULES:
        if not applies_at(r.media, PHONE):
            continue
        for p in r.parts:
            cs = compounds(norm(p))
            s = cs[-1]
            if not re.search(r":first-(?:child|of-type)", s) or tag_of(s) not in ("td", "", "*"):
                continue
            named = {c for comp in cs for c in classes_of(comp)} | {"#" + i for comp in cs for i in ids_of(comp)}
            if any(n in named if n else not named for n in names):
                decls += r.decls
    pos, left, bg = last(decls, "position"), last(decls, "left", "inset-inline-start"), last(decls, "background", "background-color")
    assert pos == "sticky" and px(left) == 0 and bg == "var(--surface)", \
        (f"{wrap}'s tables on a phone: first column position {pos}, left {left}, background {bg}; "
         f"want position: sticky; left: 0; background: var(--surface)")


# ------------------------------------------------------------------ 11. radii
def test_only_three_radii():
    bad = []
    for r in RULES + INLINE:
        for p, v in r.decls:
            if not re.fullmatch(r"border(?:-[a-z]+)*-radius", p):
                continue
            for w in words(v.replace("/", " ")):
                if w in ("50%", "inherit") or re.fullmatch(r"var\(--r-(?:1|2|pill)\)", w):
                    continue
                if px(w) is None or px(w) not in RADII:
                    bad.append(where(r, p, v))
                    break
    assert not bad, report(bad, "radii other than 6px, 10px, 999px, 50% or var(--r-*)")


# ------------------------------------------------------------------ 12. line length
def test_explanations_keep_to_72_characters_a_line():
    bad = []
    for sel in EXPLANATIONS:
        if not styled([sel]):
            continue
        mw = last(cascade([sel]), "max-width", "max-inline-size")
        m = re.fullmatch(r"(\d*\.?\d+)ch", mw or "")
        if not m or float(m.group(1)) > MEASURE:
            bad.append(f"{sel}: max-width {mw}")
    bad += [where(r, p, v) for r in RULES for p, v in r.decls
            if p in ("max-width", "max-inline-size") and re.fullmatch(r"(\d*\.?\d+)ch", v) and float(v[:-2]) > MEASURE]
    assert not bad, report(bad, f"explanations and Terms definitions wider than {MEASURE}ch")


# ------------------------------------------------------------------ 13. the current tab
def test_the_current_tab_has_two_cues():
    cur = '.nav-b[aria-current="true"]'
    base = weight_of(cascade([".nav-b"])) or "400"
    weight = weight_of(cascade([".nav-b", cur])) or base
    decls = cascade([cur])
    after = cascade([cur + "::after"])
    ink = r"var\(--(?:ink|brand-ink)\)"
    line = (re.search(rf"\b2px\b.*{ink}|{ink}.*\b2px\b", last(decls, "border-bottom") or "")
            or (px(last(decls, "border-bottom-width")) == 2 and re.fullmatch(ink, last(decls, "border-bottom-color") or ""))
            or re.search(rf"inset.*-?2px.*{ink}|{ink}.*inset.*-?2px", last(decls, "box-shadow") or "")
            or (px(last(after, "height")) == 2 and re.fullmatch(ink, last(after, "background", "background-color") or "")))
    problems = []
    if weight != "600":
        problems.append(f"its weight is {weight}, not 600")
    if base == "600":
        problems.append("the other tabs are 600 too, so weight isn't a cue (pinned: plain .nav-b at 400)")
    if not line:
        problems.append("no 2px underline in --ink or --brand-ink (border-bottom or an inset box-shadow)")
    assert not problems, f"{cur}: " + "; ".join(problems)


# ------------------------------------------------------------------ 15. panels keep their hairlines
@pytest.mark.parametrize("panel", [".fold"])
def test_panels_have_a_hairline(panel):
    border = last(cascade([panel]), "border")
    assert border and "1px" in border and "var(--line)" in border, f"{panel} has no 1px var(--line) hairline: {border}"



def test_no_box_shadow_separates_panels():
    bad = [where(r, "box-shadow", last(r.decls, "box-shadow")) for r, p in subjects_with(PANELS)
           if (last(r.decls, "box-shadow") or "none") != "none"]
    assert not bad, report(bad, "panels separated by a box-shadow")
