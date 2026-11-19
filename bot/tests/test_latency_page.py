"""The Latency tab (dashboard.html, latency.js, latency.css).

Added Oct 15, 2026, and cut down the same day to the current setup only: with less than a week of data for each, a
comparison of setups said little. A tab after Live Research draws /api/latency (test_latency_api.py) for the current setup only, fast entry, live since Oct 14,
21:04 UTC: its figures up top (median landing, each window's first order, the slowest 1 in 20, the share of contracts
filled, how many orders and windows, since when); a chart of how long after minute 8 each of its orders reached Kalshi,
one dot per order on a plain seconds scale from zero, with the median and the slowest-1-in-20 as lines; what the setup
does; where the time goes now (estimates); what could come next; and the terms. Nothing compares it with the setups
before it: no history of changes, no markers, no "x faster". Every part folds, as on the other tabs.

The page's wiring is read as text, and the two lines that choose the page run in node. latency.js runs in node after
the page's helpers and fold helpers, cut out of dashboard.html as test_live_research_page.py cuts them, with $, patch,
store, fetch, setInterval and document stood in for. The node tests skip themselves without node.

    python -m pytest tests/test_latency_page.py -q
"""
import json
import os
import re
import subprocess

import pytest

from layout import STATIC
from test_live_research_page import (HELPERS, HTML, NODE, SCRIPT, code, fold_helpers, joined, needs_node, piece, text)

HERE = STATIC   # the dashboard's pages: dashboard.html, tape.html and their .js and .css
NOW = 1792092600                      # Oct 15, 2026, 1:30 pm PT
W = 1791936000                        # Oct 14, 2026, 00:00 UTC: a window's start


def own(name):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        pytest.fail(f"{name} doesn't exist yet")
    return open(path, encoding="utf-8").read()


def body(signature):
    assert signature in SCRIPT, f"dashboard.html no longer has {signature!r}"
    return SCRIPT.split(signature)[1].split("\n}\n")[0]


def node(js):
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ------------------------------------------------------------------ dashboard.html: the tab's wiring
def test_the_nav_has_latency_after_live_research():
    r = body("function render() {")
    live = '<button class="nav-b" type="button" data-page="liveresearch" aria-current="${lab}">Live Research</button>'
    lat = '<button class="nav-b" type="button" data-page="latency" aria-current="${lat}">Latency</button>'
    assert live in r and lat in r and r.index(live) < r.index(lat)
    assert r.count("data-page=") == 3                                  # and Backtest, added Oct 28 (test_backtest_page.py)
    assert 'aria-current="${!other && m === d.mode}"' in r              # no account tab is current on either tab


def test_latency_has_its_own_section_after_live_researchs():
    main = HTML.split("<main")[1].split("</main>")[0]
    sec = '<section id="latency" aria-label="Latency" hidden></section>'
    assert sec in main and main.index('id="liveresearch"') < main.index(sec)


def test_on_latency_the_account_hides_and_only_latency_draws():
    r = body("function render() {")
    assert 'for (const id of ["hero", "chartPanel", "board", "fills", "positions", "orders", "method", "more"]) $(id).hidden = other;' in r
    assert '$("liveFolds").hidden = other;' in r
    assert '$("liveresearch").hidden = !lab;' in r and '$("latency").hidden = !lat;' in r
    assert 'document.body.classList.toggle("wide", other);' in r
    assert 'patch("banners", other ? (halted ? b[0] : "") : b.join(""));' in r
    assert "else if (lat) { if (window.latencyView) latencyView(); }" in r
    assert r.count("latencyView") == 2
    assert "if (lat) latMissing();" in r
    empty = body("function renderEmpty() {")
    assert 'if (page === "latency") return window.latencyView && latencyView();' in empty


def test_a_dashboard_that_doesnt_serve_the_script_says_restart():
    m = body("function latMissing() {")
    assert "window.latencyHtml" in m and 'patch("latency"' in m and "Restart the dashboard" in m


def test_its_script_and_styles_load_after_live_researchs():
    css, js = '<link rel="stylesheet" href="/latency.css">', '<script src="/latency.js"></script>'
    assert HTML.index('<link rel="stylesheet" href="/live_research.css">') < HTML.index(css) < HTML.index("</head>")
    assert HTML.index('<script src="/live_research.js"></script>') < HTML.index(js) < HTML.index("</body>")


def page_line():
    m = re.search(r"^let page = (.+);$", SCRIPT, re.M)
    assert m, "the page's `let page = ...;` line is gone"
    return m.group(1)


@needs_node
@pytest.mark.parametrize("stored, opens", [("latency", "latency"), ("liveresearch", "liveresearch"), ("research", "account"),
                                           (None, "account"), ("Latency", "account")])
def test_a_remembered_latency_tab_opens_again(stored, opens):
    js = (f"const store = {{ get: (k) => k === 'page' ? {json.dumps(stored)} : null }};"
          f"process.stdout.write(JSON.stringify({page_line()}));")
    assert node(js) == opens


def click_line():
    lines = [x.strip() for x in SCRIPT.splitlines() if "t.dataset.page" in x]
    assert len(lines) == 1 and lines[0].startswith("else if (t.dataset.page"), lines
    return lines[0]


@needs_node
@pytest.mark.parametrize("button, opens, saved", [("latency", "latency", "latency"), ("liveresearch", "liveresearch", "liveresearch"),
                                                  ("research", "account", None), ("other", "account", None)])
def test_the_latency_button_opens_its_tab(button, opens, saved):
    js = ("let page = 'account', saved = null, loads = 0; const store = { set: (k, v) => { if (k === 'page') saved = v; } };"
          f"const load = () => {{ loads++; }}; const t = {{ dataset: {{ page: {json.dumps(button)} }} }};"
          f"if (false) {{}} {click_line()}"
          "process.stdout.write(JSON.stringify([page, saved, loads]));")
    assert node(js) == [opens, saved, 1 if saved else 0]


# ------------------------------------------------------------------ latency.js and latency.css, read as text
@needs_node
def test_latency_js_parses():
    own("latency.js")
    r = subprocess.run([NODE, "--check", os.path.join(HERE, "latency.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_it_is_one_closure_with_a_pure_markup_function_and_a_view():
    js = own("latency.js")
    assert "(() => {" in js and '"use strict";' in js and js.rstrip().endswith("})();")
    assert "window.latencyHtml = " in js and "window.latencyView = " in js
    assert re.search(r'patch\("latency", (window\.)?latencyHtml\(', js)


def test_it_fetches_only_its_own_route_never_a_cached_copy():
    js = code(own("latency.js"))
    assert re.findall(r"\bfetch\(([^)]*)\)", js) == ['"/api/latency", { cache: "no-store" }']
    assert set(re.findall(r"[\"'`](/api/[^\"'`?]*)", js)) == {"/api/latency"}


def test_it_polls_every_15_seconds_only_while_its_tab_and_the_browser_tab_are_visible():
    js = code(own("latency.js"))
    assert re.search(r"\b15000\b", js)
    assert '!$("latency").hidden && !document.hidden' in js


def test_it_ends_by_drawing_itself_if_the_page_is_already_on_its_tab():
    assert re.search(r'if \(page === "latency" && data\) window\.latencyView\(\);[^\n]*\n\}\)\(\);$', own("latency.js").rstrip())


def test_its_styles_cant_reach_the_other_pages():
    css = re.sub(r"/\*.*?\*/", "", own("latency.css"), flags=re.S)
    selectors = [one.strip() for sel in re.findall(r"(?:^|[{}])\s*([^{}@;\s][^{}]*?)\s*\{", css) for one in sel.split(",")]
    assert selectors
    for one in selectors:
        assert one.startswith(("#latency", ".lat-")), one


# ------------------------------------------------------------------ latency.js, run in node
def page_globals():
    helpers = "\n".join([*(piece(rf"^const {n} = [^\n]*$") for n in ("esc", "nf", "zero", "money", "signed", "pct", "spct",
                                                                     "tone", "cents", "hhmm", "sym", "count")),
                         piece(r"^const when = \(t\) => \{.*?^\};$")])
    folds_js, missing = fold_helpers()
    assert not missing, missing
    names = ", ".join(HELPERS)
    return f"""
"use strict";
globalThis.window = globalThis;
const __in = JSON.parse(__input);
let __log = [];
const __intervals = [], __els = {{}}, __queue = (__in.fetches || []).slice();
const __el = (id) => __els[id] || (__els[id] = {{ id, hidden: id === "latency" ? !!__in.latHidden : false, innerHTML: "" }});
const $ = (id) => __el(id);
const {{ {names} }} = (() => {{
{helpers}
return {{ {names} }};
}})();
function patch(id, html) {{ __log.push(["patch", id, html]); __el(id).innerHTML = html; return true; }}
const store = {{ get: (k) => {{ const s = __in.storage || {{}}; return Object.prototype.hasOwnProperty.call(s, k) ? s[k] : null; }},
                set: (k, v) => {{ __log.push(["store.set", k, v]); }} }};
{folds_js}__log = [];
function setInterval(fn, ms) {{ __log.push(["setInterval", ms]); __intervals.push([fn, ms]); return __intervals.length; }}
const document = {{ hidden: false, readyState: "complete" }};
async function fetch(url, opts) {{
  __log.push(["fetch", url, opts === undefined ? null : JSON.parse(JSON.stringify(opts))]);
  const r = __queue.length > 1 ? __queue.shift() : __queue[0];
  if (!r) return new Promise(() => {{}});
  if (r.throw) throw new TypeError(r.throw);
  return {{ ok: r.status >= 200 && r.status < 300, status: r.status, json: async () => r.body }};
}}
let page = __in.page, data = __in.data;
const __settle = async () => {{ for (let i = 0; i < 200; i++) await null; }};
async function __main() {{
  const out = {{ load: __log, intervals: __intervals.map((i) => i[1]) }};
  __log = []; await __settle(); out.afterLoad = __log;
  out.steps = [];
  for (const s of __in.steps || []) {{
    __log = [];
    if ("latHidden" in s) __el("latency").hidden = s.latHidden;
    if ("docHidden" in s) document.hidden = s.docHidden;
    if (s.do === "tick") {{ for (const [f, ms] of __intervals) f(); }}
    else if (s.do === "view") window.latencyView();
    await __settle();
    out.steps.push(__log);
  }}
  out.html = (__in.replies || []).map((r) => window.latencyHtml(r));
  return JSON.stringify(out);
}}
"""


RUNNER = """
const vm = require("vm"), fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ console, __input: JSON.stringify(input) });
vm.runInContext(input.pageJs, ctx, { filename: "dashboard.html (page globals)" });
vm.runInContext(fs.readFileSync(input.file, "utf8"), ctx, { filename: "latency.js" });
vm.runInContext("__main()", ctx).then((out) => process.stdout.write(out),
  (e) => { process.stderr.write(String((e && e.stack) || e)); process.exitCode = 1; });
"""


def run(replies=(), page="account", data=None, fetches=(), steps=(), lat_hidden=False, storage=None):
    if not NODE:
        pytest.skip("node isn't installed")
    own("latency.js")
    payload = {"pageJs": page_globals(), "file": os.path.join(HERE, "latency.js"), "replies": list(replies), "page": page,
               "data": data, "fetches": list(fetches), "steps": list(steps), "latHidden": lat_hidden, "storage": storage or {}}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, "TZ": "America/Los_Angeles"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def draw(*replies):
    out = run(replies=replies)["html"]
    for m in out:
        assert isinstance(m, str) and m.strip(), "latencyHtml() returned nothing"
        bad = re.search(r"\b(NaN|undefined|null|Infinity)\b", text(m))
        assert not bad, f"a missing number reached the page as {bad.group(0)!r}"
    return out if len(out) > 1 else out[0]


def shows(markup, s):
    return s in text(markup) or s in joined(markup)


def orders_on(day_start, landings, share=0.6):
    """One order per window from day_start, each landing as given."""
    return [[day_start + i * 900 + 480 + x, x, share, 10] for i, x in enumerate(landings)]


SINCE = 1792011884                     # fast entry went live: Oct 14, 2026, 2:04:44 PM PT
FIRST = SINCE - SINCE % 900 + 900      # the first window after it: Oct 14, 2:15 PM PT
ORDERS = orders_on(FIRST, [0.35, 0.32, 1.43, 0.31]) + orders_on(FIRST + 18 * 3600, [0.29, 0.36], 0.7)
FIG = {"orders": 6, "windows": 6, "median": 0.34, "first": 0.31, "p95": 1.16, "filled": 0.52}
SETUP = {"title": "Fast entry", "what": "The bot wakes at minute 8 on Kalshi's clock and sends <every> order of a window together."}
WHERE = [{"step": "Wake up", "lo": 0, "hi": 25, "what": "Windows timers can fire late."},
         {"step": "Order trip", "lo": 30, "hi": 48, "what": "One way from a home connection to Ohio."}]
NEXT = [{"title": "Timing log", "what": "Time each step of a real burst.", "saves": "Finds the gap", "status": "Not built"},
        {"title": "Ohio server", "what": "Run the bot next to Kalshi.", "saves": "85–120 ms", "status": "Idea"}]
FULL = {"mode": "live-prod", "now": NOW, "mark": 480, "since": SINCE, "setup": SETUP, "orders": ORDERS, "figures": FIG,
        "where": WHERE, "next": NEXT}
KEYS = ["lat.chart", "lat.where", "lat.next", "lat.terms"]
NONE = {"orders": 0, "windows": 0, "median": None, "first": None, "p95": None, "filled": None}


@needs_node
def test_before_the_first_answer_it_says_its_loading():
    assert shows(draw(None), "Loading")


@needs_node
def test_a_dashboard_without_the_route_says_restart_it():
    m = draw({"httpStatus": 404})
    assert shows(m, "Restart the dashboard")


@needs_node
def test_an_error_is_shown_escaped():
    m = draw({"error": "boom <b>"})
    assert "boom &lt;b&gt;" in m and "<b>boom" not in m


@needs_node
def test_with_no_orders_yet_it_says_so():
    m = draw({**FULL, "orders": [], "figures": NONE})
    assert shows(m, "No orders yet") and 'class="lat-dot"' not in m


@needs_node
def test_the_chart_has_a_dot_per_order_a_median_line_and_a_slow_line():
    m = draw(FULL)
    assert "<svg" in m and 'class="lat-chart"' in m
    assert m.count('class="lat-dot"') == len(ORDERS)
    assert m.count('class="lat-med"') == 1 and m.count('class="lat-p95"') == 1   # the median and the slowest 1 in 20
    assert 'class="lat-mark"' not in m and 'class="lat-tag"' not in m             # no markers for older changes
    assert re.search(r'<svg[^>]*role="img"[^>]*aria-label="[^"]*0\.34 s[^"]*"', m)   # the label says the median


def grid(m):
    """The scale's labelled lines: [(label, y)], top of the chart first."""
    ys = [float(y) for y in re.findall(r'<line class="lat-grid"[^>]*\sy1="([-\d.]+)"', m)]
    labels = re.findall(r'<text class="lat-ax"[^>]*text-anchor="end">([^<]+)</text>', m)
    assert ys and len(ys) == len(labels), (ys, labels)
    return sorted(zip(labels, ys), key=lambda p: p[1])


@needs_node
def test_the_scale_is_plain_seconds_from_zero_evenly_spaced():
    g = grid(draw(FULL))                                                  # slowest 1.43 s: up to 2 s
    assert [label for label, _ in g] == ["2 s", "1.5 s", "1 s", "0.5 s", "0 s"]
    gaps = [b - a for (_, a), (_, b) in zip(g, g[1:])]
    assert max(gaps) - min(gaps) < 0.2                                    # linear: equal steps, not a log scale


@needs_node
@pytest.mark.parametrize("slowest, top", [(0.45, "0.5 s"), (0.9, "1 s"), (1.43, "2 s"), (4.2, "5 s"), (7.0, "10 s")])
def test_the_scale_tops_out_just_over_the_slowest_order(slowest, top):
    g = grid(draw({**FULL, "orders": orders_on(FIRST, [0.3, slowest])}))
    assert g[0][0] == top and g[-1][0] == "0 s"


@needs_node
def test_dots_stay_inside_the_plot_whatever_the_landing():
    odd = {**FULL, "orders": [[FIRST + 480 - 0.2, -0.2, 0.5, 4], [FIRST + 1380, 0, 0.5, 4], [FIRST + 2280 + 500, 500, None, None]] + ORDERS}
    m = draw(odd)
    ys = [float(y) for y in re.findall(r'class="lat-dot"[^>]*\scy="([-\d.]+)"', m)]
    box = re.search(r'class="lat-plot" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', m)
    assert box and len(ys) == len(odd["orders"])
    top, height = float(box.group(2)), float(box.group(4))
    assert all(top <= y <= top + height for y in ys)


@needs_node
def test_the_figures_up_top_are_the_current_setups_own():
    m = draw(FULL)
    for s in ("0.34 s", "0.31 s", "1.16 s", "52%", "Oct 14"):            # median, first order, slowest 1 in 20, filled, since
        assert shows(m, s), s
    assert shows(m, "6 orders") and shows(m, "6 windows")


@needs_node
def test_nothing_compares_it_with_older_setups():
    m = draw(FULL)
    t = text(m) + " " + joined(m)
    for gone in ("faster", "×", "before", "Every change", "day before", "logarithmic", "Log scale", "numbered", "Live launch"):
        assert gone.lower() not in t.lower(), gone
    assert "lat.steps" not in m


@needs_node
def test_it_says_what_the_current_setup_does_escaped():
    m = draw(FULL)
    assert shows(m, "Fast entry") and "sends &lt;every&gt; order" in m and "<every>" not in m


@needs_node
def test_a_reply_without_figures_still_draws_its_dots():
    m = draw({**FULL, "figures": None, "setup": None})
    assert m.count('class="lat-dot"') == len(ORDERS)


@needs_node
def test_where_the_time_goes_and_whats_next_are_shown():
    m = draw(FULL)
    assert shows(m, "Wake up") and shows(m, "0–25 ms") and shows(m, "30–48 ms")
    assert shows(m, "Timing log") and shows(m, "85–120 ms") and shows(m, "Not built")
    where = m.split('data-fold-key="lat.where"')[1].split('data-fold-key="lat.next"')[0]
    assert shows(where, "0.31 s")                                         # against each window's first order, measured


@needs_node
def test_every_part_folds_and_open_all_carries_their_keys():
    m = draw(FULL)
    for k in KEYS:
        assert f'data-fold-key="{k}"' in m
    assert f'data-fold-keys="{" ".join(KEYS)}"' in m


@needs_node
def test_a_viewers_fold_choice_sticks():
    out = run(replies=[FULL], storage={"folds": json.dumps({"lat.chart": False})})["html"][0]
    assert re.search(r'data-fold-key="lat\.chart" data-open="false"', out)


@needs_node
def test_the_view_draws_at_once_then_reads_its_route():
    out = run(page="latency", steps=[{"do": "view"}], fetches=[{"status": 200, "body": FULL}])
    calls = out["steps"][0]
    assert ["fetch", "/api/latency", {"cache": "no-store"}] in calls
    drawn = [c for c in calls if c[0] == "patch" and c[1] == "latency"]
    assert drawn and 'class="lat-chart"' in drawn[-1][2]


@needs_node
def test_it_polls_every_15_seconds_and_only_while_seen():
    out = run(steps=[{"do": "tick"}, {"latHidden": True, "do": "tick"}, {"latHidden": False, "docHidden": True, "do": "tick"}],
              fetches=[{"status": 200, "body": FULL}])
    assert out["intervals"] == [15000]
    fetched = [any(c[0] == "fetch" for c in s) for s in out["steps"]]
    assert fetched == [True, False, False]


@needs_node
def test_a_failed_read_says_so_on_the_page():
    out = run(page="latency", steps=[{"do": "view"}], fetches=[{"throw": "offline"}])
    drawn = [c for c in out["steps"][0] if c[0] == "patch" and c[1] == "latency"]
    assert drawn and "reach the dashboard" in text(drawn[-1][2]) and "offline" in text(drawn[-1][2])
