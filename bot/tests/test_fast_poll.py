"""The dashboard polling as fast as it safely goes: shorter timers and matching server caches,
and no new Kalshi calls.

The page polls as fast as it safely can. Its timers:

- the Live tab's own read of /api/state, every second through a named constant, STATE_EVERY = 1000 (it was 5 s);
- the Live tab's market board, every 250 ms (BOARD_EVERY; it was 1 s);
- the navbar balance, still every second (BALANCE_EVERY = 1000: each read is a Kalshi request);
- the Live Research tab, every 2 s (live_research.js EVERY; it was 5 s).
(Historical Research, which asked whether a study file changed at most every 5 s, left the page on Oct 15.)

The server's caches follow them, so each poll reads something fresh: the board's feed and the research folder are cached
0.2 s (RESEARCH_EVERY, under the board's 250 ms), the Live Research answer 2 s (LIVE_RESEARCH_EVERY). The caches in front
of Kalshi (the navbar balance 0.5 s, the account 10 s, the open bets' marks 10 s, the value history 30 s) don't move.

No pile-up: a read of /api/state still running makes the next tick skip, the way pollBoard and pollBalance skip with a
busy flag (a slow answer never stacks a second request behind it), and a failed read frees the next one. The footer
says the page "refreshes every second" (and whose clock it's on: test_real_clock.py).

The timers are read as text. The rest runs in node: dashboard.html's whole script in a small stand-in page whose fetch
answers only when the test says so (so a read can be left running) and whose timers fire only when the test says so;
the footer, as the whole page draws it in test_folds_live.py's stand-in browser (test_real_clock.draw); and
live_research.js with the page's helpers (as test_live_research_page.py loads it) on a clock the test moves. The node tests skip themselves without node.

    python -m pytest tests/test_fast_poll.py -q
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from layout import STATIC

HERE = STATIC   # the dashboard's pages: dashboard.html, tape.html and their .js and .css
HTML = open(os.path.join(HERE, "dashboard.html"), encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)   # the page's own script, as test_frontend.py cuts it
LR_JS = open(os.path.join(HERE, "live_research.js"), encoding="utf-8").read()
PY = open(dashboard.__file__, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")


def const(src, name):
    """The number a top-level `const NAME = <number>;` sets, or None while there's no such line."""
    m = re.search(rf"^\s*const {name} = (\d+(?:\.\d+)?);", src, re.M)
    return float(m.group(1)) if m else None


def comment_beside(name):
    """The comment on the line dashboard.py sets NAME on."""
    m = re.search(rf"^{name} = [^#\n]*#(.*)$", PY, re.M)
    assert m, f"dashboard.py has no commented {name} line"
    return m.group(1)


# ------------------------------------------------------------------ the page's timers, read as text
def test_the_live_tab_reads_its_state_every_second_through_state_every():
    assert re.search(r"^const STATE_EVERY = 1000;", SCRIPT, re.M), "dashboard.html has no `const STATE_EVERY = 1000;`"
    assert re.search(r"^setInterval\((?:load|\(\) => load\(\)), STATE_EVERY\);", SCRIPT, re.M), "load isn't on STATE_EVERY"
    assert not re.search(r"setInterval\([^;]*\b5000\)", SCRIPT), "a 5-second timer is left in the page"


def test_the_board_reads_its_markets_every_250_ms():
    assert re.search(r"^const BOARD_EVERY = 250;", SCRIPT, re.M), f"BOARD_EVERY is {const(SCRIPT, 'BOARD_EVERY')}, not 250"
    assert re.search(r"^setInterval\(pollBoard, BOARD_EVERY\);", SCRIPT, re.M)


def test_the_navbar_balance_still_reads_every_second():
    """Each read of the navbar balance is a Kalshi request, so it stays at one a second."""
    assert re.search(r"^const BALANCE_EVERY = 1000;", SCRIPT, re.M)
    assert re.search(r"^setInterval\(pollBalance, BALANCE_EVERY\);", SCRIPT, re.M)


def test_the_live_research_tab_reads_every_2_seconds():
    assert re.search(r"^const EVERY = 2000;", LR_JS, re.M), f"live_research.js EVERY is {const(LR_JS, 'EVERY')}, not 2000"
    assert re.search(r"setInterval\(.*, EVERY\);", LR_JS)


# ------------------------------------------------------------------ the server's caches
def test_the_boards_feed_and_the_live_research_answer_are_cached_shorter():
    assert dashboard.RESEARCH_EVERY == pytest.approx(0.2)
    assert dashboard.LIVE_RESEARCH_EVERY == pytest.approx(2)


def test_each_cache_is_no_longer_than_the_poll_it_serves():
    """So each poll reads something fresh: the board's feed under the board's poll, the Live Research answer under its tab's."""
    board, every = const(SCRIPT, "BOARD_EVERY"), const(LR_JS, "EVERY")
    assert board and every, "BOARD_EVERY or live_research.js EVERY is gone"
    assert dashboard.RESEARCH_EVERY <= board / 1000
    assert dashboard.LIVE_RESEARCH_EVERY <= every / 1000


def test_the_caches_in_front_of_kalshi_dont_move():
    """No new Kalshi calls: the navbar balance, the account, the open bets' marks and the value history keep their caches."""
    assert dashboard.BALANCE_EVERY == 0.5
    assert dashboard.ACCOUNT_EVERY == 10
    assert dashboard.HISTORY_EVERY == 30
    assert re.search(r'cached\(\("marks", .*\), 10,', PY), "the open bets' marks are no longer cached 10 s"


# ------------------------------------------------------------------ wording
def test_no_text_or_comment_still_says_the_old_timers():
    assert "refreshes every 5" not in HTML and "5-second" not in HTML, "dashboard.html still says the 5-second refresh"
    assert not re.search(r"\b5(?:-second| seconds?| s)\b", LR_JS), "live_research.js still says it reads every 5 s"
    assert "every 5" not in comment_beside("ACCOUNT_EVERY"), "ACCOUNT_EVERY's comment still says the page refreshes every 5"
    assert "every 5" not in comment_beside("LIVE_RESEARCH_EVERY"), "LIVE_RESEARCH_EVERY's comment still says every 5"
    assert "1-second" not in comment_beside("RESEARCH_EVERY"), "RESEARCH_EVERY's comment still says a 1-second poll"


@needs_node
def test_the_live_research_tabs_stamp_says_every_2_seconds():
    from test_live_research_page import FULL, draw, text
    shown = text(draw(FULL))
    assert "every 2 s" in shown and "every 5 s" not in shown


# ------------------------------------------------------------------ the footer, as the whole page draws it in node
def foot(bal):
    """The footer's text as the page draws it, with the navbar balance read (bal) or not, from a server that sends no
    clock: dashboard.html's whole script in test_folds_live.py's stand-in browser (test_real_clock.draw), so the
    footer's words can come from any helper the page has."""
    if not NODE:
        pytest.skip("node isn't installed")
    from test_real_clock import draw
    return draw(balance=bal).by_id("foot").text()


@needs_node
def test_the_footer_says_the_page_refreshes_every_second():
    """... and, with no clock from the server, that the times are this PC's clock."""
    assert re.fullmatch(r"Updated .+? · refreshes every second · the balance up top every second · clock from this PC"
                        r" · times are your local time", foot({"value": 517.73})), foot({"value": 517.73})
    assert re.fullmatch(r"Updated .+? · refreshes every second · clock from this PC · times are your local time",
                        foot(None)), foot(None)


# ------------------------------------------------------------------ load() never overlaps: the whole page script in node
# A small stand-in page: elements are plain objects, localStorage a map, and the timers only recorded. fetch() answers
# only when a step says so, so a read of /api/state can be left running. render() is swapped for a stand-in that, as the
# real one does, takes the mode from the answer, so the steps can't trip over the drawing.
STAND_IN = r"""
"use strict";
const __in = JSON.parse(__input);
globalThis.window = globalThis;
const __fetches = [], __renders = [], __intervals = [], __listeners = {}, __errors = [];
const __store = new Map(Object.entries(__in.storage || {}));
const __classes = (set) => ({ add: (...c) => c.forEach((x) => set.add(x)), remove: (...c) => c.forEach((x) => set.delete(x)),
  toggle: (c, on) => { const v = on === undefined ? !set.has(c) : !!on; if (v) set.add(c); else set.delete(c); return v; },
  contains: (c) => set.has(c) });
const __els = {};
const __el = (id) => __els[id] || (__els[id] = { id, hidden: false, innerHTML: "", textContent: "", className: "", title: "",
  dataset: {}, style: {}, clientWidth: 900, classList: __classes(new Set()), setAttribute() {}, getAttribute: () => null,
  removeAttribute() {}, addEventListener() {}, removeEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
  closest: () => null, focus() {}, appendChild() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 300 }) });
const __body = new Set();
globalThis.document = { hidden: false, activeElement: null, body: { classList: __classes(__body) }, documentElement: { dataset: {} },
  getElementById: __el, querySelector: () => null, querySelectorAll: () => [],
  addEventListener: (type, fn) => { (__listeners[type] = __listeners[type] || []).push(fn); }, removeEventListener() {} };
globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {};
globalThis.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} });
globalThis.localStorage = { getItem: (k) => (__store.has(k) ? __store.get(k) : null), setItem: (k, v) => { __store.set(k, String(v)); },
  removeItem: (k) => { __store.delete(k); } };
globalThis.setInterval = (fn, ms) => { __intervals.push([fn, ms]); return __intervals.length; };
globalThis.clearInterval = () => {};
globalThis.setTimeout = () => 0; globalThis.clearTimeout = () => {};
globalThis.requestAnimationFrame = () => 0; globalThis.cancelAnimationFrame = () => {};
globalThis.fetch = (url, opts) => new Promise((resolve, reject) => { __fetches.push({ url: String(url), resolve, reject, settled: false }); });
"""

DRIVER = r"""
render = function () { if (data && data.modes && data.modes.length) mode = data.mode; __renders.push(data ? data.mode : null); };
const __state = () => __fetches.filter((f) => f.url.startsWith("/api/state"));
const __modeOf = (url) => new URLSearchParams(url.split("?")[1] || "").get("mode");
function __reply(f, status) {
  f.settled = true;
  const body = { mode: __modeOf(f.url) || "live-prod", modes: ["live-prod", "live-demo"], now: 1791751200 };
  f.resolve({ ok: status >= 200 && status < 300, status, json: async () => body, text: async () => JSON.stringify(body) });
}
const __settle = async () => { for (let r = 0; r < 4; r++) { for (let i = 0; i < 50; i++) await null; await new Promise((res) => __setImmediate(res)); } };
async function __main() {
  await __settle();
  const out = { loadError: __loadError, intervals: __intervals.map((i) => i[1]), steps: [] };
  for (const s of __in.steps) {
    let error = null;
    try {
      if (s.do === "load") load();                                   // another call: the tick, a click, the halt button
      else if (s.do === "every") {                                   // the clock passes s.ms: each timer of that period fires
        for (const [fn, ms] of __intervals.slice()) if (ms === s.ms) { try { fn(); } catch (e) { __errors.push(String(e)); } }
      } else if (s.do === "answer" || s.do === "answerAll" || s.do === "fail") {
        const open = __state().filter((f) => !f.settled);
        for (const f of s.do === "answerAll" ? open : open.slice(0, 1)) {
          if (s.do === "fail") { f.settled = true; f.reject(new TypeError("Failed to fetch")); }   // the network failed
          else __reply(f, s.status || 200);
        }
      } else if (s.do === "pick") {                                  // a click on a mode's tab, through the page's own handler
        const t = { dataset: { mode: s.mode }, getAttribute: () => null };
        for (const fn of __listeners.click || []) fn({ target: { closest: () => t }, preventDefault() {} });
      }
    } catch (e) { error = String((e && e.stack) || e); }
    await __settle();
    out.steps.push({ error, state: __state().map((f) => f.url), renders: __renders.slice(), body: [...__body], mode });
  }
  return JSON.stringify(out);
}
"""

RUNNER = """
const vm = require("vm"), fs = require("fs");
const input = fs.readFileSync(0, "utf8"), p = JSON.parse(input);
const ctx = vm.createContext({ console, URLSearchParams, __input: input, __setImmediate: setImmediate, __loadError: null });
process.on("unhandledRejection", () => {});                         // a timer the page set off may fail in the stand-in page
vm.runInContext(p.standIn, ctx, { filename: "stand-in-page.js" });
try { vm.runInContext(p.script, ctx, { filename: "dashboard.html" }); }
catch (e) { ctx.__loadError = String((e && e.stack) || e); }
vm.runInContext(p.driver, ctx, { filename: "driver.js" });
vm.runInContext("__main()", ctx).then((out) => process.stdout.write(out),
  (e) => { process.stderr.write(String((e && e.stack) || e)); process.exitCode = 1; });
"""


def page(*steps, mode="live-prod"):
    """The Live tab opened (its first /api/state read left running), then each step: {"do": "load"} another call to
    load(); {"do": "every", "ms": n} each timer of that period fires; {"do": "answer"} the oldest running read answers
    (200, or "status"), {"do": "answerAll"} every running read in turn, {"do": "fail"} the oldest fails; {"do": "pick",
    "mode": m} a click on a mode's tab. After each: the /api/state reads made so far, the modes drawn, the body's classes."""
    if not NODE:
        pytest.skip("node isn't installed")
    payload = {"standIn": STAND_IN, "script": '"use strict";' + SCRIPT, "driver": DRIVER, "storage": {"mode": mode},
               "steps": list(steps)}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["loadError"] is None, out["loadError"]
    for s in out["steps"]:
        assert s["error"] is None, s["error"]
    return out


def reads(out):
    """How many /api/state reads had started after each step."""
    return [len(s["state"]) for s in out["steps"]]


LOAD, ANSWER, FAIL, SECOND = {"do": "load"}, {"do": "answer"}, {"do": "fail"}, {"do": "every", "ms": 1000}


@needs_node
def test_the_page_reads_its_state_at_once_and_again_each_second():
    out = page(ANSWER, SECOND, ANSWER, SECOND)
    assert reads(out) == [1, 2, 2, 3], "the Live tab doesn't read /api/state each second"
    assert set(out["steps"][-1]["state"]) == {"/api/state?mode=live-prod"}
    assert 5000 not in out["intervals"]


@needs_node
def test_a_read_still_running_makes_the_next_tick_skip():
    """A slow /api/state answer: the ticks and calls meanwhile start no second read; once it's in, the next tick reads."""
    out = page(SECOND, SECOND, LOAD, LOAD, ANSWER, SECOND)
    assert reads(out) == [1, 1, 1, 1, 1, 2], "load() started a second /api/state read while one was still running"
    assert out["steps"][4]["renders"] == ["live-prod"]                      # the slow answer is still drawn, once


@needs_node
@pytest.mark.parametrize("failed", [FAIL, {"do": "answer", "status": 500}], ids=["network", "http-500"])
def test_a_failed_read_frees_the_next_one(failed):
    out = page(LOAD, failed, LOAD)
    assert reads(out)[0] == 1, "load() started a second /api/state read while one was still running"
    assert reads(out) == [1, 1, 2], "after a failed read the next load() didn't read again: the busy flag stayed set"
    assert "offline" in out["steps"][1]["body"]                              # the failure still dims the page
    assert out["steps"][1]["renders"] == []


@needs_node
def test_a_mode_picked_while_a_read_is_running_is_the_one_that_shows():
    """The busy flag mustn't lose a click: the tab picked while the last mode's read is still out ends up on screen
    (and in the next reads), not overwritten by that older answer."""
    out = page({"do": "pick", "mode": "live-demo"}, {"do": "answerAll"}, SECOND, LOAD, {"do": "answerAll"})
    last = out["steps"][-1]
    assert last["mode"] == "live-demo", f"the page went back to {last['mode']}"
    assert last["renders"][-1] == "live-demo"
    assert last["state"][-1] == "/api/state?mode=live-demo"


# ------------------------------------------------------------------ the Live Research tab's beat, on a clock the test moves
# live_research.js loaded as test_live_research_page.py loads it, on the tab, with Date.now() under the test's control.
# Each second the page's own refresh (STATE_EVERY) calls liveResearchView(), and the tab's own timer fires on its beat.
CADENCE = r"""
let __t = 1791751200000;
Date.now = () => __t;
async function __cadence() {
  await __settle();
  for (let s = 1; s <= __in.seconds; s++) {
    __t += 1000;
    window.liveResearchView();                                          // the page's own refresh, once a second
    for (const [f, ms] of __intervals) if ((s * 1000) % ms === 0) f();  // the tab's own timer, on its beat
    await __settle();
  }
  return JSON.stringify({ reads: __log.filter((c) => c[0] === "fetch").length, intervals: __intervals.map((i) => i[1]) });
}
"""

CADENCE_RUNNER = """
const vm = require("vm"), fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ console, __input: JSON.stringify(input) });
vm.runInContext(input.pageJs, ctx, { filename: "dashboard.html (page globals)" });
vm.runInContext(fs.readFileSync(input.file, "utf8"), ctx, { filename: "live_research.js" });
vm.runInContext("__cadence()", ctx).then((out) => process.stdout.write(out),
  (e) => { process.stderr.write(String((e && e.stack) || e)); process.exitCode = 1; });
"""


@needs_node
def test_the_live_research_tab_reads_every_2_seconds_though_the_page_redraws_it_every_second():
    """Its answer is cached 2 s on the server, so it reads every 2 s, not on each of the page's 1-second redraws:
    in 10 seconds on the tab (counting the read as it opens), 6 reads."""
    from test_live_research_page import page_globals
    payload = {"pageJs": page_globals() + CADENCE, "file": os.path.join(HERE, "live_research.js"), "page": "liveresearch",
               "data": {"mode": "live-prod"}, "fetches": [{"status": 200, "body": {"error": "x"}}], "steps": [],
               "replies": [], "times": [], "lrHidden": False, "storage": {}, "seconds": 10}
    r = subprocess.run([NODE, "-e", CADENCE_RUNNER], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", timeout=60, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert 5 <= out["reads"] <= 6, f"{out['reads']} reads of /api/live-research in 10 s on the tab, not one every 2 s"
