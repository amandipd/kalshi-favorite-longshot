"""The Historical Research tab is gone from the dashboard.

On Oct 15, 2026 the tab's results were saved and the tab was taken off the page. The results were saved first, as an offline copy of the tab with its data. Then
the tab left the page: no navbar button, no section, no research.js or research.css in bot/, nothing served for them,
and a page remembered as "research" from before opens the Live tab. The navbar keeps the account tabs and Live
Research, and from Oct 15 the Latency tab after it (test_latency_page.py has that tab's own checks). The server's data routes, /api/research and /api/research/stamp, are backend and stay (test_dashboard_more.py,
test_losses_server.py and the rest still cover them); /api/research/live is the Live tab board's feed and stays too.

The page is read as text; the two lines that choose the page (the remembered one on load, and a click on a data-page
button) are run for real in node. The node tests skip themselves without node.

    python -m pytest tests/test_no_historical_research.py -q
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from layout import STATIC, TESTS

HTML = open(os.path.join(STATIC, "dashboard.html"), encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)   # the page's own script
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")
GONE = re.compile(r"(?<!live_)research\.(?:js|css)\b")   # the tab's two files; live_research.js/.css are Live Research's
FILE = re.compile(r"(?<!live_)(?<!/)research\.(?:js|css)\b")   # ... named as files ("/research.js", a URL the server must refuse, is fine)


def read(name, folder=STATIC):
    with open(os.path.join(folder, name), encoding="utf-8") as f:
        return f.read()


def body(signature):
    """A function of the page's script, from its signature to its closing brace at the start of a line."""
    assert signature in SCRIPT, f"dashboard.html no longer has {signature!r}"
    return SCRIPT.split(signature)[1].split("\n}\n")[0]


def node(js):
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ------------------------------------------------------------------ the page
def test_the_page_has_no_historical_research_anywhere():
    assert "Historical Research" not in HTML                       # no button, no section label, no comment pointing at it
    assert 'data-page="research"' not in HTML and 'id="research"' not in HTML and '$("research")' not in SCRIPT
    assert "researchView" not in HTML                              # nothing waits for research.js to draw
    assert 'page === "research"' not in SCRIPT and "page === 'research'" not in SCRIPT
    assert not GONE.search(HTML), GONE.search(HTML)


def test_it_loads_only_the_scripts_and_styles_of_the_tabs_that_are_still_here():
    """Live Research, Latency and Backtest (Oct 28). The removed tab's own two files are what must not appear."""
    assert re.findall(r"<script[^>]+src=\"([^\"]+)\"", HTML) == ["/live_research.js", "/latency.js",
                                                                  "/backtest.js"]
    assert re.findall(r"<link[^>]+rel=\"stylesheet\"[^>]+href=\"([^\"]+)\"", HTML) == ["/live_research.css", "/latency.css",
                                                                                        "/backtest.css", "/exchange.css"]
    assert HTML.index("</script>") < HTML.index('<script src="/live_research.js"></script>')   # still after the page's own


def test_the_navbar_has_the_account_tabs_then_the_three_page_tabs_only():
    r = body("function render() {")
    live = '<button class="nav-b" type="button" data-page="liveresearch" aria-current="${lab}">Live Research</button>'
    lat = '<button class="nav-b" type="button" data-page="latency" aria-current="${lat}">Latency</button>'
    assert live in r and r.index('data-mode="${esc(m)}"') < r.index(live) < r.index(lat)
    bt = '<button class="nav-b" type="button" data-page="backtest" aria-current="${bt}">Backtest</button>'
    assert bt in r and r.index(lat) < r.index(bt)
    assert r.count("data-page=") == 3                 # Live Research, Latency and Backtest are the only page buttons
    assert 'aria-current="${!other && m === d.mode}"' in r         # no account tab is current on either


def test_live_research_still_hides_the_account_and_widens_the_page():
    r = body("function render() {")
    assert 'lab = page === "liveresearch", lat = page === "latency", bt = page === "backtest";' in r
    assert "const other = lab || lat || bt;" in r
    assert 'for (const id of ["hero", "chartPanel", "board", "fills", "positions", "orders", "method", "more"]) $(id).hidden = other;' in r
    assert '$("liveresearch").hidden = !lab;' in r
    assert 'document.body.classList.toggle("wide", other);' in r
    assert 'patch("banners", other ? (halted ? b[0] : "") : b.join(""));' in r    # only a halt up top, as before
    assert "if (lab) { if (window.liveResearchView) liveResearchView(); }" in r
    assert re.search(r"\baway\b(?=\s*(?:[=;,)?:]|&&|\|\|))", SCRIPT) is None   # no `away` variable: one tab off the account now, "lab" says it
    empty = body("function renderEmpty() {")
    assert 'if (page === "liveresearch") return window.liveResearchView && liveResearchView();' in empty


def page_line():
    m = re.search(r"^let page = (.+);$", SCRIPT, re.M)
    assert m, "the page's `let page = ...;` line is gone"
    return m.group(1)


@needs_node
@pytest.mark.parametrize("stored, opens", [("research", "account"), ("liveresearch", "liveresearch"), ("latency", "latency"),
                                           ("account", "account"), (None, "account"), ("anything", "account")])
def test_a_remembered_page_opens_live_research_latency_or_the_account(stored, opens):
    """A browser that last showed Historical Research remembers "research": it now opens the Live tab."""
    js = (f"const store = {{ get: (k) => k === 'page' ? {json.dumps(stored)} : null }};"
          f"process.stdout.write(JSON.stringify({page_line()}));")
    assert node(js) == opens


def click_line():
    lines = [x.strip() for x in SCRIPT.splitlines() if "t.dataset.page" in x]
    assert len(lines) == 1 and lines[0].startswith("else if (t.dataset.page"), lines   # one branch, after the mode tabs'
    return lines[0]


@needs_node
@pytest.mark.parametrize("button, opens, saved", [("liveresearch", "liveresearch", "liveresearch"), ("latency", "latency", "latency"),
                                                  ("research", "account", None), ("other", "account", None)])
def test_only_live_research_and_latency_open_from_a_page_button(button, opens, saved):
    js = ("let page = 'account', saved = null, loads = 0; const store = { set: (k, v) => { if (k === 'page') saved = v; } };"
          f"const load = () => {{ loads++; }}; const t = {{ dataset: {{ page: {json.dumps(button)} }} }};"
          f"if (false) {{}} {click_line()}"
          "process.stdout.write(JSON.stringify([page, saved, loads]));")
    assert node(js) == [opens, saved, 1 if saved else 0]


# ------------------------------------------------------------------ the server and the folder
def test_the_server_serves_only_the_files_of_the_tabs_that_are_still_here():
    assert set(dashboard.ASSETS) == {"/live_research.js", "/live_research.css", "/latency.js", "/latency.css",
                                     "/backtest.js", "/backtest.css",
                                     "/exchange.css",   # the Live tab's exchange skin, Oct 30
                                     "/tape_fmt.js", "/tape_panels.js", "/tape.js",   # the Tape page at /tape, Nov 6
                                     "/tape.css", "/tape_panels.css"}
    assert not GONE.search(open(dashboard.__file__, encoding="utf-8").read())   # its comments don't point at them either


def test_the_tabs_files_are_gone_from_the_folder():
    for name in ("research.js", "research.css", "folds_baseline_research.json"):
        for folder in (STATIC, TESTS):
            assert not os.path.exists(os.path.join(folder, name)), name


def test_no_test_still_reads_the_tabs_files():
    me = os.path.basename(__file__)
    left = {f: FILE.findall(read(f, TESTS)) for f in sorted(os.listdir(TESTS))
            if f.endswith(".py") and f != me and FILE.search(read(f, TESTS))}
    assert left == {}


def test_live_researchs_own_files_dont_point_at_the_tab():
    for name in ("live_research.js", "live_research.css"):
        text = read(name)
        assert "Historical Research" not in text and not GONE.search(text), name


def test_the_studys_data_routes_stay():
    """Only the page went: the server still answers the study and its stamp, and the Live board's feed."""
    src = open(dashboard.__file__, encoding="utf-8").read()
    for route in ('"/api/research"', '"/api/research/stamp"', '"/api/research/live"'):
        assert f"if u.path == {route}:" in src, route
    assert callable(dashboard.study) and callable(dashboard.stamp)
