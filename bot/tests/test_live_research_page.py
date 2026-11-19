"""The Live Research tab: the +1¢ limit experiment, followed live (dashboard.html, live_research.js, live_research.css).

The bot's buy is an immediate-or-cancel order (it takes what the book has at once and cancels the rest), and its limit
(the most it will pay) can sit 1¢ over the ask it saw (bot.LIMIT_UP; off for now, measured on paper first: see
test_shadow_page.py). A tab beside the account tabs follows that experiment from
the ledger, through the dashboard's /api/live-research: how much more of each order fills, what the extra contracts
(the ones bought above the ask it saw) earn in ¢ per $10 staked with a 95% range, and how that compares with what the
research predicted. The tab is a list of experiment cards, so a second experiment can join it later with a key of its
own in the same reply.

The page's side is checked two ways. Its wiring in dashboard.html (its tab, its section, when it is drawn, no live bot
beside it any more, the files it loads, the "How it trades" rule) is read as text; test_no_historical_research.py has
the rest of the navbar and the page choice since the Historical Research tab left on Oct 15. live_research.js is
loaded whole in node, the way the browser loads it after the page's own script: the page helpers it may use (esc,
money, cents, when, ...) and, once the page has them, its shared fold helpers (FOLDS, folds, foldOpen, fold,
foldsButton) are cut out of dashboard.html, and $, patch, store, fetch, setInterval and document are
stood in for. So the tests can poll it, open its tab, and hand liveResearchHtml() replies shaped like the server's:
none yet, a dashboard not restarted since the route was added (404), an error, an experiment not started, too early
to tell, one with numbers, and one carrying a later experiment's key it doesn't know yet. They check what it says, not
how it lays it out: a panel's heading is an <h3> or a fold's title, and test_folds_live_research.py checks the folds. The node tests skip themselves without node.

    python -m pytest tests/test_live_research_page.py -q
"""

import copy
import functools
import html
import json
import os
import re
import shutil
import subprocess

import pytest

from layout import STATIC

HERE = STATIC   # the dashboard's pages: dashboard.html, tape.html and their .js and .css
HTML = open(os.path.join(HERE, "dashboard.html"), encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)   # the page's own script, as test_frontend.py cuts it
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")

HEADINGS = ("The +1¢ limit experiment", "Fill rates", "What the extra cent bought", "Predictions vs live",
            "Latest experiment orders", "Terms")


def own(name):
    """One of the tab's own files beside dashboard.html: a plain failure, not a crash, while it doesn't exist yet."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        pytest.fail(f"{name} doesn't exist yet")
    return open(path, encoding="utf-8").read()


def body(signature):
    """A function of the page's script, from its signature to its closing brace at the start of a line."""
    assert signature in SCRIPT, f"dashboard.html no longer has {signature!r}"
    return SCRIPT.split(signature)[1].split("\n}\n")[0]


# ------------------------------------------------------------------ dashboard.html: the Live Research tab
def test_the_nav_has_live_research_after_the_modes():
    r = body("function render() {")
    live = '<button class="nav-b" type="button" data-page="liveresearch" aria-current="${lab}">Live Research</button>'
    assert live in r
    assert r.index('data-mode="${esc(m)}"') < r.index(live)
    assert ">Research</button>" not in SCRIPT                                   # the old label is gone
    assert 'aria-current="${!other && m === d.mode}"' in r                     # no mode tab is current on Live Research (or Latency)


def test_a_market_on_the_board_links_to_kalshi_instead_of_opening_historical_research():
    """Historical Research lost its Markets view, so the board's market name is a link to that market on Kalshi."""
    assert ('<a class="bd-mk" href="${esc(kalshiUrl(m.ticker))}" target="_blank" rel="noopener" '
            'title="${esc(m.label)} on Kalshi">${esc(m.label)}</a>') in body("function boardBlock() {")
    assert "boardMk" not in SCRIPT and "researchOpen" not in HTML              # no click on the board opens a research tab


def test_live_research_has_its_own_section():
    main = HTML.split("<main")[1].split("</main>")[0]
    assert '<section id="liveresearch" aria-label="Live Research" hidden></section>' in main


def test_live_research_is_drawn_only_on_its_own_tab():
    r = body("function render() {")
    assert "if (lab) { if (window.liveResearchView) liveResearchView(); }" in r
    assert r.count("liveResearchView") == 2                                      # nowhere else in render()
    empty = body("function renderEmpty() {")                                     # no account yet: the tab still draws
    assert 'if (page === "liveresearch") return window.liveResearchView && liveResearchView();' in empty


def test_no_live_bot_sits_beside_the_research_tabs():
    """The live-bot sidebar is gone from both research tabs: no element, no function, no
    styles, and no room kept for it, so Live Research uses the page's full width (the navbar still shows the live value)."""
    assert not re.search(r"liveside|liveSide", HTML, re.I)                      # the <aside id="liveside">, liveSide(), .liveside
    styles = HTML + own("live_research.css")
    assert not re.search(r"\.ls-[\w-]", styles), re.findall(r"\.ls-[\w-]+", styles)   # its .ls-* rules
    assert not re.search(r"body\.wide\s*\{[^}]*padding-right", HTML)           # the right padding kept for it
    assert "var(--ls-w)" not in styles


def test_its_script_and_styles_load_after_the_pages_own():
    css, js = '<link rel="stylesheet" href="/live_research.css">', '<script src="/live_research.js"></script>'
    assert css in HTML and js in HTML
    assert HTML.index("</style>") < HTML.index(css) < HTML.index("</head>")
    assert HTML.index("</script>\n" + js) < HTML.index("</body>")


def test_how_it_trades_says_the_limit_is_a_cent_over_the_ask_it_saw():
    """Once the live limit is on (L.limitUp > 0); while it's off the +1¢ runs on paper (test_shadow_page.py)."""
    m = body("function method(L) {")
    ioc = next((x for x in m.split("`") if "immediate-or-cancel" in x and "${cents(L.limitUp)}" in x), "")
    assert "${cents(L.limitUp)}" in ioc and "${cents(L.hi)}" in ioc             # 1¢ over what it saw, at most 99.9¢
    assert "nothing waits on the book" in ioc
    assert "L.limitUp > 0" in m                                                  # only once the bot sets LIMIT_UP
    limits = re.search(r"const LIMITS = \{(.*?)\};", SCRIPT, re.S).group(1)
    assert re.search(r"\blimitUp: 0(?:\.0+)?(?![.\d])", limits)                 # the fallback until the server says: off


def test_the_orders_block_no_longer_says_an_order_fills_at_the_price_it_saw():
    block = SCRIPT[SCRIPT.index("function method(L) {"):SCRIPT.index("function table(id, head, rows, empty) {")]
    assert "at that price" not in block and "at the best price the bot just saw:" not in block   # its comment and empty text
    empty = re.search(r'["`](No orders yet\..*?)["`]', block, re.S)
    assert empty and "immediate-or-cancel" in empty.group(1) and re.search(r"limit|1¢", empty.group(1))


# ------------------------------------------------------------------ live_research.js, read as text
def code(js):
    """The script without its comments (block comments and whole-line // comments)."""
    return re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S), flags=re.M)


@needs_node
def test_live_research_js_parses():
    own("live_research.js")
    r = subprocess.run([NODE, "--check", os.path.join(HERE, "live_research.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_it_is_one_closure_with_a_pure_markup_function_and_a_view():
    js = own("live_research.js")
    assert "(() => {" in js and '"use strict";' in js and js.rstrip().endswith("})();")   # an IIFE
    assert "window.liveResearchHtml = " in js and "window.liveResearchView = " in js
    assert re.search(r'patch\("liveresearch", (window\.)?liveResearchHtml\(', js)          # the view draws with the pure function


def test_each_experiment_is_one_card_renderer_in_a_list():
    """A later experiment ("fast entry") is one more function in the list, beside the +1¢ limit's."""
    assert "const CARDS = [" in code(own("live_research.js"))


def test_it_fetches_only_its_own_route_and_never_a_cached_copy():
    js = code(own("live_research.js"))
    assert re.findall(r"\bfetch\(([^)]*)\)", js) == ['"/api/live-research", { cache: "no-store" }']
    assert set(re.findall(r"[\"'`](/api/[^\"'`?]*)", js)) == {"/api/live-research"}


def test_it_polls_every_2_seconds_only_while_its_tab_and_the_browser_tab_are_visible():
    js = code(own("live_research.js"))
    assert re.search(r"\b2000\b", js) and not re.search(r"\b5000\b", js)
    assert '!$("liveresearch").hidden && !document.hidden' in js


def test_it_ends_by_drawing_itself_if_the_page_is_already_on_its_tab():
    js = own("live_research.js").rstrip()
    assert re.search(r'if \(page === "liveresearch" && data\) window\.liveResearchView\(\);[^\n]*(\n\}\)\(\);)?$', js)


# ------------------------------------------------------------------ live_research.css
def test_the_live_research_styles_cant_reach_the_account_pages():
    """Every rule, inside a media query or not, is scoped to the tab: #liveresearch or an .lr- class."""
    css = re.sub(r"/\*.*?\*/", "", own("live_research.css"), flags=re.S)
    selectors = [one.strip() for sel in re.findall(r"(?:^|[{}])\s*([^{}@;\s][^{}]*?)\s*\{", css) for one in sel.split(",")]
    assert selectors, "found no rules: the pattern needs updating"
    for one in selectors:
        if one in ("from", "to") or re.fullmatch(r"\d+(\.\d+)?%", one):
            continue                                                            # keyframe steps
        assert one.startswith(("#liveresearch", ".lr-")), one


# ------------------------------------------------------------------ live_research.js, run in node
def piece(pattern):
    m = re.search(pattern, SCRIPT, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


HELPERS = ("esc", "money", "signed", "pct", "spct", "tone", "cents", "count", "hhmm", "when", "sym")

# The shared fold helpers dashboard.html gives the Live and Live Research pages; live_research.js
# draws its folds with them. They are cut out by name with whatever else of the page's script they lean on (parse, ...),
# except the globals page_globals() stands in for.
FOLD_NAMES = ("FOLDS", "folds", "foldOpen", "fold", "foldsButton")
GIVEN = {*HELPERS, "$", "patch", "store", "page", "data", "document", "window", "fetch", "setInterval", "clearInterval",
         "setTimeout", "clearTimeout"}

# Where each of the page's top-level statements ends: the first line at which it compiles on its own and the next line
# doesn't carry it on (".then(", "+ more", ...). Node's own parser, so strings, templates and regexes can't fool it.
CUTTER = r"""
const vm = require("vm");
const { lines, starts } = JSON.parse(require("fs").readFileSync(0, "utf8"));
const goesOn = (s) => s != null && /^\s*(?:\.|\?|:|\+|-|\*|%|&&|\|\||,|=)/.test(s);
const end = (i) => {
  for (let j = i; j < lines.length; j++) {
    try { new vm.Script(lines.slice(i, j + 1).join("\n")); } catch (e) { continue; }
    let k = j + 1;
    while (k < lines.length && !lines[k].trim()) k++;
    if (!goesOn(lines[k])) return j;
  }
  return -1;
};
process.stdout.write(JSON.stringify(starts.map(end)));
"""


def top_level():
    """Each name dashboard.html's script declares at its top level -> the line its statement starts on."""
    out = {}
    for i, line in enumerate(SCRIPT.split("\n")):
        fn = re.match(r"(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(", line)
        names = [fn.group(1)] if fn else re.findall(r"(?:^(?:const|let|var)\s+|,\s*)([A-Za-z_$][\w$]*)\s*=(?![=>])", line) \
            if re.match(r"(?:const|let|var)\s", line) else []
        for n in names:
            out.setdefault(n, i)
    return out


@functools.lru_cache(maxsize=None)
def fold_helpers():
    """The page's fold helpers as one block of script that declares those it has globally, and the names it lacks.
    The block is "" while dashboard.html has none of them (the page before the folds)."""
    top = top_level()
    have, missing = [n for n in FOLD_NAMES if n in top], tuple(n for n in FOLD_NAMES if n not in top)
    if not have:
        return "", missing
    lines = SCRIPT.split("\n")
    starts = sorted(set(top.values()))
    r = subprocess.run([NODE, "-e", CUTTER], input=json.dumps({"lines": lines, "starts": starts}), capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    ends = dict(zip(starts, json.loads(r.stdout)))
    take, todo = set(), list(have)
    while todo:                                                                 # each helper, then what it leans on
        n = todo.pop()
        if n in GIVEN or n not in top or top[n] in take:
            continue
        i = top[n]
        assert ends[i] >= 0, f"can't tell where dashboard.html's statement declaring {n} ends"
        take.add(i)
        src = "\n".join(lines[i:ends[i] + 1])
        bare = re.sub(r"(?<![:\\])//[^\n]*", "", re.sub(r"/\*.*?\*/", "", src, flags=re.S))
        todo += re.findall(r"(?<![\w$.])[A-Za-z_$][\w$]*", bare)
    body = "\n".join("\n".join(lines[i:ends[i] + 1]) for i in sorted(take))
    names = ", ".join(have)
    return f"const {{ {names} }} = (() => {{\n{body}\nreturn {{ {names} }};\n}})();\n", missing


def said(name):
    return name + ("()" if name[0].islower() and name != "folds" else "")


def need_folds():
    """Fail plainly, not with a crash, while dashboard.html lacks a fold helper."""
    missing = fold_helpers()[1]
    if missing:
        pytest.fail(f"dashboard.html has no {', '.join(said(n) for n in missing)} yet")


def page_globals():
    """The globals live_research.js may use, as dashboard.html's script leaves them: the page's own helpers, cut out
    of it (money and the others lean on nf and zero, which stay private here), its fold helpers once it has them (cut
    out by name, with parse and the rest they lean on), and stand-ins for $, patch, store, setInterval, fetch and
    document that log every call. A fetch answers with the scripted replies in turn; store answers from the input's
    "storage" (what localStorage holds: "folds" is the viewer's fold choices), else null."""
    helpers = "\n".join([*(piece(rf"^const {n} = [^\n]*$") for n in ("esc", "nf", "zero", "money", "signed", "pct", "spct",
                                                                     "tone", "cents", "hhmm", "sym", "count")),
                         piece(r"^const when = \(t\) => \{.*?^\};$")])
    names = ", ".join(HELPERS)
    folds_js, missing = fold_helpers()
    js = code(own("live_research.js"))
    uses = [n for n in missing if re.search(rf"\b{n}\s*\(" if said(n).endswith("()") else rf"\b{n}\s*[\[.]", js)]
    if uses:
        pytest.fail(f"dashboard.html has no {', '.join(said(n) for n in uses)} yet, and live_research.js uses it")
    return f"""
"use strict";
globalThis.window = globalThis;
const __in = JSON.parse(__input);
let __log = [];
const __intervals = [], __els = {{}}, __queue = (__in.fetches || []).slice();
const __el = (id) => __els[id] || (__els[id] = {{ id, hidden: id === "liveresearch" ? !!__in.lrHidden : false, innerHTML: "",
  dataset: {{}}, addEventListener() {{}}, removeEventListener() {{}}, querySelector: () => null, querySelectorAll: () => [],
  setAttribute() {{}}, getAttribute: () => null, classList: {{ add() {{}}, remove() {{}}, toggle() {{}}, contains: () => false }} }});
const $ = (id) => {{ __log.push(["$", id]); return __el(id); }};
const {{ {names} }} = (() => {{
{helpers}
return {{ {names} }};
}})();
function patch(id, html) {{ __log.push(["patch", id, html]); __el(id).innerHTML = html; return true; }}
const store = {{ get: (k) => {{ __log.push(["store.get", k]); const s = __in.storage || {{}}; return Object.prototype.hasOwnProperty.call(s, k) ? s[k] : null; }},
                set: (k, v) => {{ __log.push(["store.set", k, v]); }} }};
{folds_js}__log = [];                                                   // the page's own setup (folds read from store) isn't live_research.js's
function setInterval(fn, ms) {{ __log.push(["setInterval", ms]); __intervals.push([fn, ms]); return __intervals.length; }}
function clearInterval() {{ __log.push(["clearInterval"]); }}
function setTimeout(fn, ms) {{ __log.push(["setTimeout", ms]); return 0; }}
function clearTimeout() {{ __log.push(["clearTimeout"]); }}
const __doc = {{ hidden: false, addEventListener() {{}}, removeEventListener() {{}} }};
const document = new Proxy(__doc, {{ get: (t, k) => {{ __log.push(["document." + String(k)]); return t[k]; }} }});
async function fetch(url, opts) {{
  __log.push(["fetch", url, opts === undefined ? null : JSON.parse(JSON.stringify(opts))]);
  const r = __queue.length > 1 ? __queue.shift() : __queue[0];
  if (!r) return new Promise(() => {{}});                       // nothing scripted: the answer never comes
  if (r.throw) throw new TypeError(r.throw);                     // the network failed
  return {{ ok: r.status >= 200 && r.status < 300, status: r.status, json: async () => r.body, text: async () => JSON.stringify(r.body) }};
}}
let page = __in.page, data = __in.data;
const __settle = async () => {{ for (let i = 0; i < 200; i++) await null; }};
async function __main() {{
  const out = {{ load: __log, intervals: __intervals.map((i) => i[1]) }};
  __log = []; await __settle(); out.afterLoad = __log;
  out.steps = [];
  for (const s of __in.steps || []) {{
    __log = [];
    if ("page" in s) page = s.page;
    if ("lrHidden" in s) __el("liveresearch").hidden = s.lrHidden;
    if ("docHidden" in s) __doc.hidden = s.docHidden;
    if (s.do === "tick") {{ for (const [f, ms] of __intervals) {{ if (ms === 2000) f(); }} }}
    else if (s.do === "view") window.liveResearchView();
    await __settle();
    out.steps.push(__log);
  }}
  out.html = [];
  for (const r of __in.replies || []) {{
    if (typeof window.liveResearchHtml !== "function") throw new Error("live_research.js doesn't set window.liveResearchHtml");
    __log = [];
    out.html.push({{ markup: window.liveResearchHtml(r), calls: __log.map((c) => c[0]) }});
  }}
  out.times = (__in.times || []).map((t) => [when(t), hhmm(t)]);
  return JSON.stringify(out);
}}
"""


# The page's globals run first, then live_research.js as a script of its own in the same realm (as two <script> tags
# share one page), then the steps; the browser's `window` is that realm's global object.
RUNNER = """
const vm = require("vm"), fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ console, __input: JSON.stringify(input) });
vm.runInContext(input.pageJs, ctx, { filename: "dashboard.html (page globals)" });
vm.runInContext(fs.readFileSync(input.file, "utf8"), ctx, { filename: "live_research.js" });
vm.runInContext("__main()", ctx).then((out) => process.stdout.write(out),
  (e) => { process.stderr.write(String((e && e.stack) || e)); process.exitCode = 1; });
"""


def run(replies=(), page="account", data=None, fetches=(), steps=(), times=(), lr_hidden=False, storage=None):
    if not NODE:
        pytest.skip("node isn't installed")
    own("live_research.js")
    payload = {"pageJs": page_globals(), "file": os.path.join(HERE, "live_research.js"), "replies": list(replies),
               "page": page, "data": data, "fetches": list(fetches), "steps": list(steps), "times": list(times),
               "lrHidden": lr_hidden, "storage": storage or {}}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def norm(s):
    return re.sub(r"[\s   ]+", " ", s)


def text(markup):
    """What the markup reads as: each tag a space, entities decoded, odd spaces made plain."""
    return norm(html.unescape(re.sub(r"<[^>]+>", " ", markup)))


def joined(markup):
    """The same with tags simply dropped, so "<b>+12.3</b>¢" reads "+12.3¢"."""
    return norm(html.unescape(re.sub(r"<[^>]+>", "", markup)))


def shows(markup, s):
    return s in text(markup) or s in joined(markup)


def esc(s):
    """The page's esc()."""
    return "".join({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}.get(c, c) for c in str(s))


def has_num(markup, n):
    """n on its own, as a count reads (12 or 12.0, not 112, 0.12 or 12.5)."""
    return re.search(rf"(?<![\d.,]){re.escape(str(n))}(?:\.0+)?(?![\d,]|\.\d)", text(markup)) is not None


def share(markup, v):
    """v as pct() writes it, to one place or none (0.7349: 73.5% or 73%)."""
    written = [f"{v * 100:.{dp}f}%" for dp in (1, 0)]
    return any(re.search(rf"(?<![\d.]){re.escape(w)}", t) for w in written for t in (text(markup), joined(markup)))


def has_dec(markup, s):
    """A decimal such as "9.6" on its own (not inside 79.65)."""
    return any(re.search(rf"(?<![\d.]){re.escape(s)}(?!\d)", t) for t in (text(markup), joined(markup)))


def draw_all(*replies):
    out = [h["markup"] for h in run(replies=replies)["html"]]
    for m in out:
        assert isinstance(m, str) and m.strip(), "liveResearchHtml() returned nothing"
        bad = re.search(r"\b(NaN|undefined|null|Infinity)\b", text(m))
        assert not bad, f"a missing number reached the page as {bad.group(0)!r}"
    return out


def draw(reply):
    return draw_all(reply)[0]


# A panel's heading: an <h3>, or a fold's title (<h2 class="fold-t"><button ...>chevron + title</button></h2>).
HEADING = r'<h3\b[^>]*>(.*?)</h3>|<h2\b[^>]*\bclass="[^"]*\bfold-t\b[^"]*"[^>]*>(.*?)</h2>'
ABOUT_HEAD = "How it's measured"   # each card's fold of its explanations and caveat, part of its head


def is_about(heading):
    return heading.replace("’", "'") == ABOUT_HEAD


def h3s(markup):
    """Each panel heading (an <h3>, or a fold's title): where it starts and its own words (a count or note nested in it,
    or a fold's chevron, is not part of the heading)."""
    out = []
    for m in re.finditer(HEADING, markup, re.S):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        inner = re.sub(r"^\s*<button\b[^>]*>(.*)</button>\s*$", r"\1", inner, flags=re.S)   # a fold's title is its button's
        words = re.sub(r"<(\w+)\b[^>]*>.*?</\1>", "", inner, flags=re.S)
        out.append((m.start(), norm(html.unescape(re.sub(r"<[^>]+>", "", words))).strip()))
    return out


def section(markup, heading):
    """A panel: from its h3 to the next of the six panels' h3s. The paper card comes first and may reuse a heading, so
    it is left out: these are the live card's panels, and "Terms"."""
    if re.search(r'<article\b[^>]*\bdata-exp="shadow"', markup):
        markup = markup.replace(card(markup, "shadow"), "", 1)
    found = [(at, t) for at, t in h3s(markup) if t in HEADINGS]
    at = next((a for a, t in found if t == heading), None)
    assert at is not None, f"no <h3>{heading}</h3> panel; the headings are {[t for _, t in h3s(markup)]}"
    return markup[at:min((a for a, _ in found if a > at), default=len(markup))]


def card(markup, exp):
    """An experiment's card: <article class="lr-card" data-exp="..."> up to its own closing tag."""
    opening = re.search(rf'<article\b(?=[^>]*\bclass="[^"]*\blr-card\b)(?=[^>]*\bdata-exp="{exp}")[^>]*>', markup)
    assert opening, f'no <article class="lr-card" data-exp="{exp}"> card'
    depth = 0
    for tag in re.finditer(r"<(/?)article\b[^>]*>", markup[opening.start():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return markup[opening.start():opening.start() + tag.end()]
    pytest.fail(f'the "{exp}" card is never closed')


# ------------------------------------------------------------------ replies shaped like /api/live-research
NOW = 1791751200.0                      # Oct 11, 2026, 4:40 PM ET
STARTED = NOW - 2 * 86400 - 3 * 3600    # the first +1¢ order, two days earlier
POISON = "<img src=x onerror=alert(1)>"


def arm(orders=0, asked=0.0, filled=0.0, none=0, partial=0, full=0, avg_seen=None, avg_paid=None, settled=0.0, won=0.0,
        pnl=0.0, staked=0.0, per_ten=None, se=None):
    return {"orders": orders, "asked": asked, "filled": filled, "fillShare": filled / asked if asked else None,
            "none": none, "partial": partial, "full": full, "avgSeen": avg_seen, "avgPaid": avg_paid, "settled": settled,
            "won": won, "pnl": pnl, "staked": staked, "perTen": per_ten, "se": se}


def group(orders=0, contracts=0.0, avg_price=None, fee=0.0, break_even=None, settled=0.0, won=0.0, win_rate=None, pnl=0.0,
          staked=0.0, per_ten=None, se=None, windows=0):
    return {"orders": orders, "contracts": contracts, "avgPrice": avg_price, "fee": fee, "breakEven": break_even,
            "settled": settled, "won": won, "winRate": win_rate, "pnl": pnl, "staked": staked, "perTen": per_ten,
            "se": se, "windows": windows}


BEFORE = arm(523, 800.0, 440.0, 101, 57, 365, 0.9512, 0.9498, 430.0, 414.0, 7.42, 408.4, 18.2, 9.1)   # fills 55%
DURING = arm(412, 950.0, 712.0, 23, 61, 328, 0.9497, 0.9533, 640.0, 618.0, 6.43, 610.1, 10.5, 6.0)    # fills 74.9%
BASE = group(371, 612.0, 0.9468, 9.18, 0.9618, 550.0, 531.7, 0.9667, 2.60, 520.7, 5.0, 2.0, 98)        # 95%: +1.1 to +8.9
EXTRA = group(140, 287.0, 0.9541, 4.31, 0.9691, 251.0, 246.2, 0.9810, 2.95, 239.5, 12.3, 16.3 / 1.96, 61)   # −4.0 to +28.6
HIST = {"source": "research/kalshi_15min/lab/fills.json", "size": 30, "fillBefore": 0.4321, "fillDuring": [0.6018, 0.7349],
        "perTenBefore": 2.19, "perTenDuring": [4.27, 6.36], "extraPerTen": [9.58, 13.71]}
LIVE = {"source": "research/kalshi_15min/lab/live_fills/live_fills.json", "fillBefore": 0.5462, "orders": 205,
        "contracts": 2382.98, "pnl": -25.12, "pnlSe": 43.16, "perContractCents": -1.05, "winRate": 0.9413}
ORDERS = [   # newest first
    {"ts": NOW - 130, "ticker": "KXBTC15M-26OCT111645-45", "side": "yes", "seen": 0.93, "limit": 0.94, "asked": 23.0,
     "filled": 17.0, "base": 11.0, "extra": 6.0, "avgPaid": 0.9335, "result": "open"},
    {"ts": NOW - 1030, "ticker": "KXETH15M-26OCT111630-30", "side": "no", "seen": 0.957, "limit": 0.967, "asked": 31.0,
     "filled": 0.0, "base": 0.0, "extra": 0.0, "avgPaid": None, "result": None},              # nothing filled
    {"ts": NOW - 1930, "ticker": "KXSOL15M-26OCT111615-15", "side": "yes", "seen": 0.951, "limit": 0.961, "asked": 29.0,
     "filled": 29.0, "base": None, "extra": None, "avgPaid": 0.9552, "result": "won"},         # no fills rows: unknown
    {"ts": NOW - 2830, "ticker": "KXXRP15M-26OCT111600-00", "side": "no", "seen": 0.912, "limit": 0.922, "asked": 44.0,
     "filled": 38.0, "base": 30.0, "extra": 8.0, "avgPaid": 0.9141, "result": "lost"},
]
TOO_EARLY_TEXT = "Too early to tell: 412 of 1000 orders with the +1¢ limit so far."
FULL = {"mode": "live-prod", "now": NOW, "limitUp": 0.01, "target": 1000, "started": STARTED, "fillsRecorded": True,
        "arms": {"before": BEFORE, "during": DURING},
        "split": {"base": BASE, "extra": EXTRA, "unknown": {"orders": 6, "contracts": 73.0}},
        "verdict": {"state": "too-early", "text": TOO_EARLY_TEXT, "orders": 412, "target": 1000},
        "predictions": {"history": HIST, "live": LIVE}, "orders": ORDERS}
WAITING_TEXT = "Not started: the bot sends +1¢ limits from its next restart."
WAITING = {**FULL, "started": None, "fillsRecorded": False, "arms": {"before": BEFORE, "during": arm()},
           "split": {"base": group(), "extra": group(), "unknown": {"orders": 0, "contracts": 0.0}},
           "verdict": {"state": "waiting", "text": WAITING_TEXT, "orders": 0, "target": 1000}, "orders": []}
# Twelve orders in: no standard error yet (one window), and a server text that needs escaping and says no count itself.
EARLY_TEXT = 'Too early to tell: "so far" <so good> & counting.'
TOO_EARLY = {**FULL, "arms": {"before": BEFORE, "during": arm(12, 30.0, 26.0, 1, 2, 9, 0.951, 0.9561, 9.0, 9.0, 0.41, 8.6, 47.7, None)},
             "split": {"base": group(9, 20.0, 0.951, 0.3, 0.966, 0.0, 0.0, None, 0.0, 0.0, None, None, 0),
                       "extra": group(4, 6.0, 0.9611, 0.1, 0.9778, 6.0, 6.0, 1.0, 0.13, 5.77, 15.0, None, 1),
                       "unknown": {"orders": 0, "contracts": 0.0}},
             "verdict": {"state": "too-early", "text": EARLY_TEXT, "orders": 12, "target": 1000}, "orders": ORDERS[:1]}


def with_(reply, **changes):
    """A deep copy of a reply with some fields replaced, each named by its path (verdict__text, orders__0__ticker)."""
    out = copy.deepcopy(reply)
    for path, v in changes.items():
        *head, last = path.split("__")
        node = out
        for k in head:
            node = node[int(k)] if isinstance(node, list) else node[k]
        node[int(last) if isinstance(node, list) else last] = v
    return out


# ------------------------------------------------------------------ loading, polling, and the view
@needs_node
def test_at_load_it_only_sets_up_its_poll():
    """Loaded on the account page it touches nothing but setInterval: no element, no fetch, no drawing."""
    out = run(page="account", data={"mode": "live-prod"})
    assert 2000 in out["intervals"]
    assert {c[0] for c in out["load"]} <= {"setInterval"}, out["load"]
    assert out["afterLoad"] == []


@needs_node
def test_it_polls_only_while_its_tab_and_the_browser_tab_are_on_screen():
    out = run(page="account", data={"mode": "live-prod"}, lr_hidden=True, fetches=[{"status": 200, "body": FULL}], steps=[
        {"do": "tick"},                                                         # the account page: its tab is hidden
        {"page": "liveresearch", "lrHidden": False, "docHidden": True, "do": "tick"},   # its tab, the browser tab in the background
        {"docHidden": False, "do": "tick"},                                     # on screen
    ])
    fetched = [[c[1:] for c in step if c[0] == "fetch"] for step in out["steps"]]
    assert fetched == [[], [], [["/api/live-research", {"cache": "no-store"}]]]


def last_patch(out):
    drawn = [c[2] for calls in (out["load"], out["afterLoad"], *out["steps"]) for c in calls
             if c[0] == "patch" and c[1] == "liveresearch"]
    assert drawn, "it never drew #liveresearch"
    return drawn[-1]


@needs_node
def test_opening_on_its_tab_draws_a_loading_note_at_once_then_the_answer():
    out = run(page="liveresearch", data={"mode": "live-prod"}, fetches=[{"status": 200, "body": FULL}], steps=[{"do": "view"}])
    first = [c for c in out["load"] if c[0] == "patch" and c[1] == "liveresearch"]
    assert first and re.search(r"load", text(first[0][2]), re.I)               # before any answer: a short loading note
    fetched = [c[1:] for c in out["load"] + out["afterLoad"] if c[0] == "fetch"]
    assert fetched == [["/api/live-research", {"cache": "no-store"}]]
    assert esc(TOO_EARLY_TEXT) in last_patch(out)                               # then the answer, once it's in


@needs_node
@pytest.mark.parametrize("answer, says", [
    ({"status": 404, "body": {"error": "not found"}}, "Restart the dashboard"),   # a dashboard from before the route
    ({"status": 500, "body": {"error": "boom"}}, "Restart the dashboard"),
    ({"throw": "<b>Failed to fetch</b>"}, "&lt;b&gt;Failed to fetch&lt;/b&gt;"),   # the network: its message, escaped
    ({"status": 200, "body": {"error": "no live records yet"}}, "no live records yet"),   # the server's own error
])
def test_what_the_tab_says_when_the_answer_isnt_the_experiment(answer, says):
    m = last_patch(run(page="liveresearch", data={"mode": "live-prod"}, fetches=[answer], steps=[{"do": "view"}]))
    assert says in m and "<b>Failed" not in m


@needs_node
def test_the_markup_function_is_pure():
    """liveResearchHtml() only turns a reply into markup: no element, no fetch, no timer, no drawing."""
    for h in run(replies=[None, {"httpStatus": 404}, {"error": "x"}, WAITING, TOO_EARLY, FULL])["html"]:
        assert not [c for c in h["calls"] if c in ("$", "patch", "fetch", "setInterval", "setTimeout") or c.startswith("document.")], h["calls"]


# ------------------------------------------------------------------ liveResearchHtml(reply): before the experiment's numbers
@needs_node
def test_before_the_first_answer_it_shows_a_short_loading_note():
    assert re.search(r"load", text(draw(None)), re.I)


@needs_node
@pytest.mark.parametrize("status", [404, 500])
def test_a_non_ok_answer_says_to_restart_the_dashboard(status):
    assert "Restart the dashboard" in text(draw({"httpStatus": status}))


@needs_node
def test_an_error_is_shown_escaped():
    m = draw({"error": "<b>x</b>"})
    assert "&lt;b&gt;x&lt;/b&gt;" in m and "<b>x</b>" not in m


@needs_node
def test_before_the_restart_it_says_the_experiment_hasnt_started_but_still_shows_the_fill_rate_so_far():
    m = draw(WAITING)
    assert esc(WAITING_TEXT) in section(m, "The +1¢ limit experiment")
    extra = text(section(m, "What the extra cent bought"))                       # the experiment's own panels say so too
    assert re.search(r"n[o'’]t (yet )?(been )?started|next restart", extra, re.I), extra
    fill = section(m, "Fill rates")                                             # the before arm: every order so far
    for n in (523, 800, 440, 101, 57, 365):
        assert has_num(fill, n), n
    assert share(fill, 0.55)


@needs_node
def test_too_early_shows_the_verdict_escaped_the_count_so_far_and_every_panel():
    m = draw(TOO_EARLY)
    assert esc(EARLY_TEXT) in m and "<so good>" not in m
    assert re.search(r"(?<![\d.,])12\s*(?:of|/)\s*1,?000(?![\d,])", text(m))   # n of the 1,000-order target
    found = [t for _, t in h3s(m)]
    assert all(h in found for h in HEADINGS), found
    extra = section(m, "What the extra cent bought")
    assert shows(extra, "+15.0¢") and " to +15.0)" not in joined(extra)         # no standard error yet: no 95% range


@needs_node
@pytest.mark.parametrize("reply", [FULL, TOO_EARLY], ids=["numbers", "too-early"])
def test_the_experiment_is_one_card_headed_by_its_name(reply):
    """The tab is a list of experiment cards; the +1¢ limit's holds its panels ("Terms" may sit inside it or after)."""
    c = card(draw(reply), "limitup")
    found = [t for _, t in h3s(c)]
    assert found and found[0] == "The +1¢ limit experiment", found
    assert all(h in found for h in HEADINGS[:5]), found


@needs_node
@pytest.mark.parametrize("extra", [{"state": "waiting", "orders": 3, "note": "<b>later</b>"}, None, [1, 2]],
                         ids=["object", "null", "list"])
def test_a_later_experiments_key_doesnt_break_the_page(extra):
    """A second experiment adds its own top-level key to the same reply ("fastEntry"); until the page knows it, the
    +1¢ limit's card is drawn just the same."""
    m = draw(with_(FULL, fastEntry=extra))
    c = card(m, "limitup")
    assert esc(TOO_EARLY_TEXT) in c and all(h in [t for _, t in h3s(m)] for h in HEADINGS)
    assert "<b>later</b>" not in m


@needs_node
@pytest.mark.parametrize("state, words", [
    ("too-early", TOO_EARLY_TEXT),
    ("helping", "The extra cent is paying: the extra contracts made money, and their 95% range is above zero."),
    ("hurting", "The extra cent is losing money: the extra contracts' 95% range is below zero."),
    ("no-difference", "No clear difference: the extra contracts' 95% range includes zero."),
])
def test_every_verdict_is_shown_as_the_server_words_it(state, words):
    m = draw(with_(FULL, verdict__state=state, verdict__text=words))
    assert esc(words) in section(m, "The +1¢ limit experiment")


# ------------------------------------------------------------------ liveResearchHtml(reply): the experiment's numbers
@needs_node
def test_the_status_panel_says_when_it_started_and_how_far_along_it_is():
    out = run(replies=[FULL], times=[STARTED])
    m, (when_, hhmm_) = out["html"][0]["markup"], out["times"][0]
    status = section(m, "The +1¢ limit experiment")
    assert esc(TOO_EARLY_TEXT) in status
    assert norm(when_) in text(status) or norm(hhmm_) in text(status)
    assert re.search(r"(?<![\d.,])412\s*(?:of|/)\s*1,?000(?![\d,])", text(status))


@needs_node
def test_fill_rates_compare_before_and_with_the_extra_cent():
    fill = section(draw(FULL), "Fill rates")
    for n in (523, 800, 440, 101, 57, 365):                                     # before: orders, asked, filled, none, partial, full
        assert has_num(fill, n), n
    for n in (412, 950, 712, 23, 61, 328):                                      # during
        assert has_num(fill, n), n
    assert share(fill, 0.55) and share(fill, 712 / 950)


@needs_node
def test_the_extra_cent_panel_splits_base_extra_and_unknown_with_95_ranges():
    extra = section(draw(FULL), "What the extra cent bought")
    t = text(extra)
    assert re.search(r"\bbase\b", t, re.I) and re.search(r"\bunknown\b", t, re.I)
    for n in (612, 287, 73):                                                    # contracts: base, extra, unknown
        assert has_num(extra, n), n
    for s in ("94.7¢", "95.4¢", "$2.60", "$2.95"):                             # avg price, P&L
        assert shows(extra, s), s
    assert share(extra, 0.9667) and share(extra, 0.9810)                        # win rates ...
    assert has_dec(extra, "96.2") and has_dec(extra, "96.9")                    # ... against the break-evens
    # ¢ per $10 and its 95% range, perTen ± 1.96·se
    for s in ("+5.0¢", "(+1.1 to +8.9)", "+12.3¢", "(−4.0 to +28.6)"):
        assert shows(extra, s), s


@needs_node
def test_the_predictions_sit_beside_the_live_numbers():
    pred = section(draw(FULL), "Predictions vs live")
    assert share(pred, 0.4321) and share(pred, 0.6018) and share(pred, 0.7349)   # history: fills before, and with +1¢
    assert has_dec(pred, "9.6") and has_dec(pred, "13.7")                       # history: the extra contracts' ¢ per $10
    assert share(pred, 0.5462) and share(pred, 0.9413)                          # the live-fills replay
    assert share(pred, 712 / 950)                                               # what the experiment has filled
    assert not re.search(r"unavailable|not available", text(pred), re.I)


@needs_node
@pytest.mark.parametrize("gone, kept", [("history", (0.5462,)), ("live", (0.4321, 0.6018)), ("both", ())])
def test_a_missing_prediction_says_its_unavailable(gone, kept):
    preds = {"history": None if gone in ("history", "both") else HIST, "live": None if gone in ("live", "both") else LIVE}
    pred = section(draw(with_(FULL, predictions=preds)), "Predictions vs live")
    assert re.search(r"unavailable|not available", text(pred), re.I)
    for v in kept:
        assert share(pred, v), v


@needs_node
def test_the_latest_orders_show_what_each_saw_asked_got_and_how_it_did():
    rows = section(draw(FULL), "Latest experiment orders")
    at = [rows.find(o["ticker"]) for o in ORDERS]
    assert -1 not in at and at == sorted(at), at                               # every order, newest first
    for s in ("93¢", "94¢", "95.7¢", "96.7¢", "95.1¢", "96.1¢", "91.2¢", "92.2¢"):   # the ask it saw, and its limit
        assert shows(rows, s), s
    for n in (23, 17, 31, 29, 44, 38):                                          # asked, filled
        assert has_num(rows, n), n
    for word in ("won", "lost", "open"):
        assert re.search(rf"\b{word}\b", text(rows), re.I), word


@needs_node
def test_the_terms_panel_glosses_every_term():
    terms = text(section(draw(FULL), "Terms")).lower()
    for term in ("immediate-or-cancel", "limit", "ask it saw", "extra contract", "break-even", "¢ per $10", "95% range", "cluster"):
        assert term in terms, term


@needs_node
def test_every_server_string_is_escaped():
    """Tickers, sides, results, the verdict, the sources and the mode come from the server: none may reach the markup raw."""
    ticker = "KX" + POISON + "15M-26OCT111645-45"
    only_ticker = with_(FULL, orders__0__ticker=ticker)
    only_text = with_(FULL, verdict__text="Too early " + POISON)
    everything = with_(FULL, mode=POISON, verdict__text=POISON, verdict__state=POISON, orders__0__ticker=ticker,
                       orders__0__side=POISON, orders__0__result=POISON, predictions__history__source=POISON,
                       predictions__live__source=POISON)
    for m in draw_all(only_ticker, only_text, everything, {"error": POISON}):
        assert "<img" not in m.lower()
        assert esc(POISON) in m                                                 # shown, as text
