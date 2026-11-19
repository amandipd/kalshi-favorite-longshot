"""The Live tab folds: every long section gets one clean toggle, and nothing on the page is removed.

Calmer pages: all the content stays on the page (no number removed), with clean toggles to hide most of it.
dashboard.html gets one shared fold helper (used by the
Live tab here and by live_research.js): FOLDS, the default for every fold key on the Live and Live Research pages;
`folds`, the viewer's own choices, kept in localStorage under "folds"; foldOpen(key), the choice if there is one, else
the default; fold(key, title, body, meta, cls), the section's markup; and foldsButton(keys), the page's one quiet
"Open all / Close all" button. A fold is a heading holding one real button (a chevron and the title), the section's
meta beside it and still visible while folded, and a body that is only hidden (the `hidden` attribute): folded content
stays in the page.

What's checked here:

- the helper: the markup contract, the FOLDS table with every key's default, how a stored choice is read (bad JSON, a
  stored value that isn't an object, or a choice that isn't true/false is ignored), and the label of the Open all /
  Close all button;
- the Live tab: Positions, Live markets, Orders, How it trades and Details each fold (keys live.*), open or closed at
  first as the spec says, each header still saying its key number when folded; the hero and the chart don't fold;
  the Details rows stay rows that open one by one, and the separate "Expand all" button goes;
- behaviour: a click on a fold flips it at once in place, saves the choice and fetches nothing; the next redraws (the
  5-second refresh, the board's 1-second redraw) keep it; Open all / Close all sets every Live fold and every Details
  row; the board's header (count, streaming status, minute) keeps updating while it's folded, and its hidden body keeps
  being redrawn;
- nothing is removed: the Live tab is drawn from fixed data and its text compared, as a multiset of words with entities
  decoded, with what today's page (before the folds) drew from the same data, saved in folds_baseline_live.json. Every
  word must still be there (only the spec's control labels, like "Expand all", may change or go), and every number as
  many times or more: with the defaults, with every fold closed and with every fold open.

dashboard.html's own script is loaded whole in node inside a small stand-in DOM (it parses the markup the page writes,
answers getElementById, querySelector(All), closest, dataset, hidden, details' open, classList; runs click and toggle
events the way a browser does; and keeps a fake clock, timers, fetch and localStorage), so the tests can load the page,
click its buttons and let its timers run, then read back the page as the browser would hold it. The clock and the
time zone are fixed (TZ=America/New_York), so every run draws the same page. The node tests skip themselves without
node.

The baseline was written from the page as it was before the folds, with

    FOLDS_WRITE_BASELINE=1 python -m pytest tests/test_folds_live.py -q -k write_the_baseline

and must not be written again from a page that has the folds (that would compare the new page with itself).

    python -m pytest tests/test_folds_live.py -q
"""

import hashlib
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import types
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, add_bet, home, mode_db, order  # noqa: F401  (home is a fixture)

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = open(dashboard.PAGE, encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)   # the page's own script, as test_frontend.py cuts it
BODY = HTML.split("<body>", 1)[1].split("<script>", 1)[0]                              # the page's markup before its script
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")
BASELINE = os.path.join(HERE, "folds_baseline_live.json")
WRITE = os.environ.get("FOLDS_WRITE_BASELINE") == "1"

CLOCK = NOW + 330          # Sep 28, 2026, 3:05:30 PM ET: minute 6 of the 3:00 window, before the entry at minute 8
WIDTH = 900                # what the stand-in DOM says every box measures (the chart reads its box's width)

# ------------------------------------------------------------------ the fold table
LIVE_FOLDS = {"live.positions": True, "live.board": True, "live.fills": True, "live.orders": False, "live.method": False,
              "live.details": True}   # live.fills: the Fill rate chart, between the board and Orders
LR_FOLDS = {"lr.shadow": True, "lr.shadow.about": False, "lr.shadow.extra": True, "lr.shadow.pred": False,
            "lr.shadow.latest": False, "lr.fast": True, "lr.fast.about": False, "lr.fast.vs": True, "lr.fast.latest": False,
            "lr.limit": False, "lr.limit.about": False, "lr.limit.fills": False, "lr.limit.extra": True,
            "lr.limit.pred": False, "lr.limit.latest": False, "lr.terms": False}
TITLES = {"live.positions": "Positions", "live.board": "Live markets", "live.fills": "Fill rate", "live.orders": "Orders",
          "live.method": "How it trades", "live.details": "Details"}
DETAILS = ["numbers", "history", "stops", "settings", "account", "decisions", "markets", "errors"]   # the .acc rows today
# The only text allowed to change or go (section 2): the page's own control labels, on its buttons.
CONTROL = re.compile(r"Expand all|Collapse all|Open all|Close all|Show all [\d,]+|Show fewer|Show less"
                     r"|(?:Hide |Show )?[Cc]hart options|Hide|Show")
NOT_LIVE = {"research", "liveresearch", "latency", "liveside"}   # main's other tabs (other tests' business, and the live-bot
                                                     # sidebar while it lasts), hidden on the Live tab

def decl(src, name):
    """A top-level `const`/`let`/`function` named `name` in the page's script, through the lines that continue it (the
    next line starting at column 0 with anything but a closing bracket ends it); "" if there's none."""
    m = re.search(rf"^(?:async function|function|const|let|var) {re.escape(name)}\b", src, re.M)
    if not m:
        return ""
    lines = src[m.start():].split("\n")
    out = [lines[0]]
    for line in lines[1:]:
        if line[:1] and not line[:1].isspace() and line[:1] not in "})]":
            break
        out.append(line)
    return "\n".join(out).rstrip()


def fold_helper(src=SCRIPT):
    """The shared fold helper cut out of the page's script, for tests that run one drawing function on its own (the board,
    the orders), which draws through fold() once the page has it: every top-level declaration named fold... or FOLD...
    (FOLDS, folds, foldOpen, fold, foldsButton, ...), after the page's store and parse, which `folds` is read with.
    Empty while the page has no fold helper."""
    names = re.findall(r"^(?:async function|function|const|let|var) ((?:FOLD|[Ff]old)\w*)\b", src, re.M)
    return "\n".join([decl(src, "store"), decl(src, "parse"), *(decl(src, n) for n in names)]) if names else ""


ALL_CLOSED = {"folds": json.dumps({k: False for k in LIVE_FOLDS}), "open": "[]"}
ALL_OPEN = {"folds": json.dumps({k: True for k in LIVE_FOLDS}), "open": json.dumps(DETAILS)}


# ------------------------------------------------------------------ the fixed data the page is drawn from
def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def board_market(label, group, bid, ask, path):
    """One market as /api/research/live sends it: the favorite is the side that costs more."""
    if ask is None:
        fav = price = None
    else:
        fav = "yes" if (bid + ask) / 2 >= 0.5 else "no"
        price = ask if fav == "yes" else round(1 - bid, 4)
    return {"ticker": f"KX{label}15M-26SEP281515-15", "series": f"KX{label}15M", "label": label, "group": group,
            "yes_bid": bid, "yes_ask": ask, "last": ask, "favSide": fav, "favPrice": price, "path": path}


def climb(start, end, spread=0.01):
    """A minute-by-minute path, minutes 0 to 5, from one mid to another."""
    return [[m, round(start + (end - start) * m / 5, 4), round(start + (end - start) * m / 5 + spread, 4)] for m in range(6)]


def board_feed(now, source="stream", extra=()):
    markets = [board_market("BTC", "crypto", 0.95, 0.96, climb(0.80, 0.95)),
               board_market("ETH", "crypto", 0.06, 0.07, climb(0.30, 0.06)),          # NO is the favorite, at 94c
               board_market("SOL", "crypto", 0.71, 0.72, climb(0.62, 0.71)),
               board_market("XRP", "crypto", 0.97, 0.98, climb(0.97, 0.97)),
               board_market("DOGE", "crypto", None, None, []),                        # no price yet: last, a dash
               board_market("GOLD", "metals", 0.91, 0.93, climb(0.85, 0.91, 0.02)),
               board_market("WTI", "energy", 0.40, 0.42, climb(0.52, 0.40, 0.02)),
               board_market("RACE", "coin race", 0.98, 0.99, climb(0.90, 0.98)),     # a group the bot doesn't trade
               *extra]
    return {"heartbeat": iso(now - 2), "source": source, "streamWhy": None if source == "stream" else "the stream dropped",
            "band": [bot.LO, bot.HI], "groups": ["crypto", "metals", "energy", "coin race"], "markets": markets}


def build_state(home, monkeypatch):
    """A live account with a bit of everything (as test_frontend.py's full_state), from the real server: settled bets won
    and lost, two open bets with marks, decisions, orders that filled in full, in part, not at all, refused and
    unanswered, and a Kalshi account. The clock is CLOCK, so the server's `now` is the page's."""
    home.clock[0] = CLOCK
    db = mode_db(home, "live-prod", start=500.0)
    ago = lambda s: CLOCK - s
    settled = [("KXBTC15M-26SEP271415-15", "yes", 0.94, 5, "won", ago(25 * 3600)),   # over a day ago
               ("KXETH15M-26SEP281115-15", "yes", 0.93, 4, "won", ago(4 * 3600)),
               ("KXSOL15M-26SEP281130-30", "no", 0.91, 3, "lost", ago(3 * 3600 + 1800)),
               ("KXXRP15M-26SEP281200-00", "yes", 0.97, 6, "won", ago(3 * 3600)),
               ("KXDOGE15M-26SEP281300-00", "yes", 0.96, 2, "won", ago(2 * 3600)),
               ("KXBTC15M-26SEP281400-00", "no", 0.92, 3, "lost", ago(3600)),
               ("KXETH15M-26SEP281430-30", "yes", 0.95, 4, "won", ago(1800))]
    opened = [("KXBTC15M-26SEP281500-00", "yes", 0.95, 3), ("KXSOL15M-26SEP281500-00", "no", 0.93, 4)]
    for ticker, side, price, n, status, placed in settled:
        add_bet(db, ticker, side=side, price=price, contracts=n, status=status, placed=placed)
    for ticker, side, price, n in opened:
        add_bet(db, ticker, side=side, price=price, contracts=n, status="open", placed=ago(330 + 420))   # closed at 3:00
    decide = "INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)"
    for ticker, side, price, n, *rest in settled + [o + ("open", ago(750)) for o in opened]:
        when_ = rest[-1]
        db.execute(decide, (when_, ticker, ticker.split("-")[0], side, price, "bet", f"favorite {round(price * 100)}c, spread 1c"))
    db.execute(decide, (ago(2000), "KXSOL15M-26SEP281445-45", "KXSOL15M", "yes", 0.86, "skip", "under the 90c floor"))
    db.execute(decide, (ago(1900), "KXXRP15M-26SEP281445-45", "KXXRP15M", "yes", 0.93, "skip", "spread 3c"))
    db.execute(decide, (ago(1500), "KXHYPE15M-26SEP281445-45", "KXHYPE15M", "yes", 0.94, "error", "order failed: insufficient balance"))
    for ticker, side, price, n, status, placed in settled:
        req_side, req_price = ("bid", price) if side == "yes" else ("ask", round(1 - price, 4))
        order(db, placed, ticker, side=req_side, count=str(n), price=f"{req_price:.4f}", response=json.dumps({"fill_count": f"{n}.00"}))
    for ticker, side, price, n in opened:
        req_side, req_price = ("bid", price) if side == "yes" else ("ask", round(1 - price, 4))
        order(db, ago(750), ticker, side=req_side, count=str(n + 3), price=f"{req_price:.4f}", response=json.dumps({"fill_count": f"{n}.00"}))
    order(db, ago(1600), "KXXRP15M-26SEP281430-30", count="9", price="0.9600", response='{"fill_count": "0.00"}')   # got none
    order(db, ago(1500), "KXHYPE15M-26SEP281445-45", count="5", price="0.9400", status=400,
          response='{"error": {"message": "insufficient balance"}}')                                                  # refused
    order(db, ago(1400), "KXGOLD15M-26SEP281445-45", count="4", price="0.9200", status=None, response='"network error: timed out"')
    bot.set_meta(db, "heartbeat", CLOCK - 4)
    db.commit()
    monkeypatch.setattr(dashboard, "marks", lambda env, tickers: {"KXBTC15M-26SEP281500-00": (0.97, 0.98),
                                                                   "KXSOL15M-26SEP281500-00": (0.09, 0.10)})
    monkeypatch.setattr(dashboard, "account", lambda env: {"total": 612.34, "crypto": 600.12, "positions": 2, "held": 7.1,
                                                            "value": 619.44, "updated": CLOCK - 3})
    return dashboard.state("live-prod")


def golden():
    if not os.path.exists(BASELINE):
        pytest.fail("folds_baseline_live.json is missing: it is written once from the page as it was before the folds")
    with open(BASELINE, encoding="utf-8") as f:
        return json.load(f)


def routes(g, live=None):
    """The dashboard server's answers: the account (/api/state, with or without ?mode=; its `now` is the server's clock,
    which moves with the page's) and the board's live markets. /api/balance isn't answered, so the navbar stays empty
    and the page's foot never depends on when it would have."""
    return {"/api/state": {"status": 200, "body": g["state"], "clock": True},
            "/api/research/live": {"status": 200, "body": {"now": g["now"], "stamp": 0, "live": live or g["board"]}}}


# ------------------------------------------------------------------ the stand-in browser
DOM_JS = r"""
"use strict";
const __I = __in;
let __now = __I.now, __W = __I.width, __log = [], __errors = [], __tasks = [], __raf = [], __timers = [], __tid = 0;
const __answers = Object.assign({}, __I.answers);
const __store = new Map(Object.entries(__I.store || {}));
const __safe = (fn) => {
  try { const r = fn(); if (r && typeof r.then === "function") r.then(null, (e) => __errors.push(String((e && e.stack) || e))); }
  catch (e) { __errors.push(String((e && e.stack) || e)); }
};

// the clock: Date.now() and new Date() are the page's fixed clock, moved only by the tests
const __RealDate = Date;
class __Date extends __RealDate { constructor(...a) { if (a.length) super(...a); else super(__now); } static now() { return __now; } }
globalThis.Date = __Date;
Math.random = () => 0.5;

// ---- markup in and out
const __ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0", middot: "\u00b7", times: "\u00d7", minus: "\u2212",
  ndash: "\u2013", mdash: "\u2014", hellip: "\u2026", cent: "\u00a2", rarr: "\u2192", larr: "\u2190", uarr: "\u2191", darr: "\u2193" };
const __decode = (s) => String(s).replace(/&(#x[0-9a-f]+|#\d+|[a-z][a-z0-9]*);/gi, (m, k) => k[0] === "#"
  ? String.fromCodePoint(k[1] === "x" || k[1] === "X" ? parseInt(k.slice(2), 16) : parseInt(k.slice(1), 10)) : (__ENT[k] ?? m));
const __escText = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;");
const __escAttr = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/\u00a0/g, "&nbsp;");
const __VOID = new Set("area base br col embed hr img input link meta source track wbr".split(" "));

class __Node {}
class __Style {                                     // inline styles: kept, never drawn
  setProperty(k, v) { this[k] = String(v); } removeProperty(k) { const v = this[k]; delete this[k]; return v ?? ""; }
  getPropertyValue(k) { return this[k] ?? ""; }
}
class __Text extends __Node {
  constructor(raw) { super(); this.nodeType = 3; this.raw = raw; this.parentNode = null; }
  get nodeName() { return "#text"; }
  get textContent() { return __decode(this.raw); } set textContent(v) { this.raw = __escText(v); }
  get data() { return this.textContent; } set data(v) { this.textContent = v; }
  get nodeValue() { return this.textContent; }
  get parentElement() { const p = this.parentNode; return p && p.nodeType === 1 ? p : null; }
  closest(sel) { return this.parentElement ? this.parentElement.closest(sel) : null; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
}
function __detailsChanged(el) {                     // a details' open attribute came or went: a toggle event, as a task
  if (el.localName === "details") __tasks.push(() => __dispatch(el, __event("toggle", false)));
}
class __El extends __Node {
  constructor(tag, attrs) { super(); this.nodeType = 1; this.localName = tag.toLowerCase(); this._a = new Map(attrs || []);
    this.childNodes = []; this.parentNode = null; this.style = new __Style(); this._ls = {}; }
  get tagName() { return this.localName.toUpperCase(); }
  get nodeName() { return this.tagName; }
  get ownerDocument() { return document; }
  getAttribute(k) { k = String(k).toLowerCase(); return this._a.has(k) ? this._a.get(k) : null; }
  hasAttribute(k) { return this._a.has(String(k).toLowerCase()); }
  setAttribute(k, v) { k = String(k).toLowerCase(); const had = this._a.has(k); this._a.set(k, String(v)); if (k === "open" && !had) __detailsChanged(this); }
  removeAttribute(k) { k = String(k).toLowerCase(); const had = this._a.delete(k); if (k === "open" && had) __detailsChanged(this); }
  toggleAttribute(k, force) { const on = force === undefined ? !this.hasAttribute(k) : !!force;
    if (on && !this.hasAttribute(k)) this.setAttribute(k, ""); else if (!on) this.removeAttribute(k); return on; }
  getAttributeNames() { return [...this._a.keys()]; }
  get attributes() { return [...this._a].map(([name, value]) => ({ name, value })); }
  get id() { return this.getAttribute("id") || ""; } set id(v) { this.setAttribute("id", v); }
  get className() { return this.getAttribute("class") || ""; } set className(v) { this.setAttribute("class", v); }
  get title() { return this.getAttribute("title") || ""; } set title(v) { this.setAttribute("title", v); }
  get hidden() { return this.hasAttribute("hidden"); } set hidden(v) { this.toggleAttribute("hidden", !!v); }
  get open() { return this.hasAttribute("open"); } set open(v) { this.toggleAttribute("open", !!v); }
  get disabled() { return this.hasAttribute("disabled"); } set disabled(v) { this.toggleAttribute("disabled", !!v); }
  get classList() {
    const el = this, list = () => el.className.split(/\s+/).filter(Boolean);
    const put = (a) => { if (a.length || el.hasAttribute("class")) el.setAttribute("class", a.join(" ")); };
    return { contains: (c) => list().includes(c), add: (...cs) => put([...new Set([...list(), ...cs])]),
      remove: (...cs) => put(list().filter((x) => !cs.includes(x))),
      toggle: (c, f) => { const on = f === undefined ? !list().includes(c) : !!f; put(on ? [...new Set([...list(), c])] : list().filter((x) => x !== c)); return on; },
      replace: (a, b) => { const l = list(); if (!l.includes(a)) return false; put(l.map((x) => (x === a ? b : x))); return true; },
      item: (i) => list()[i] ?? null, forEach: (fn) => list().forEach(fn), get length() { return list().length; },
      get value() { return el.className; }, [Symbol.iterator]: () => list()[Symbol.iterator]() };
  }
  get dataset() {
    const el = this, attr = (k) => "data-" + String(k).replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
    return new Proxy({}, {
      get: (t, k) => (typeof k === "string" && el.hasAttribute(attr(k)) ? el.getAttribute(attr(k)) : undefined),
      set: (t, k, v) => { el.setAttribute(attr(k), v); return true; },
      has: (t, k) => typeof k === "string" && el.hasAttribute(attr(k)),
      deleteProperty: (t, k) => { el.removeAttribute(attr(k)); return true; },
      ownKeys: () => [...el._a.keys()].filter((a) => a.startsWith("data-")).map((a) => a.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())),
      getOwnPropertyDescriptor: (t, k) => (el.hasAttribute(attr(k)) ? { value: el.getAttribute(attr(k)), enumerable: true, configurable: true, writable: true } : undefined),
    });
  }
  get innerHTML() { return this.childNodes.map(__ser).join(""); }
  set innerHTML(h) { for (const c of this.childNodes) c.parentNode = null; this.childNodes = []; for (const n of __parse(String(h))) this.appendChild(n); }
  get outerHTML() { return __ser(this); }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(v) { for (const c of this.childNodes) c.parentNode = null; this.childNodes = []; if (String(v ?? "") !== "") this.appendChild(new __Text(__escText(v))); }
  get innerText() { return this.textContent; } set innerText(v) { this.textContent = v; }
  get children() { return this.childNodes.filter((c) => c.nodeType === 1); }
  get childElementCount() { return this.children.length; }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { const k = this.children; return k[k.length - 1] || null; }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get parentElement() { const p = this.parentNode; return p && p.nodeType === 1 ? p : null; }
  get nextElementSibling() { const p = this.parentNode; if (!p) return null; const k = p.children; return k[k.indexOf(this) + 1] || null; }
  get previousElementSibling() { const p = this.parentNode; if (!p) return null; const k = p.children; return k[k.indexOf(this) - 1] || null; }
  get nextSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) + 1] || null : null; }
  get isConnected() { let x = this; while (x.parentNode) x = x.parentNode; return x === document; }
  get ownerSVGElement() { return this.parentElement ? this.parentElement.closest("svg") : null; }
  appendChild(n) {
    if (n.nodeType === 11) { for (const c of [...n.childNodes]) this.appendChild(c); return n; }
    if (n.parentNode) n.parentNode.removeChild(n);
    n.parentNode = this; this.childNodes.push(n); return n;
  }
  insertBefore(n, ref) {
    if (!ref) return this.appendChild(n);
    const nodes = n.nodeType === 11 ? [...n.childNodes] : [n];
    for (const x of nodes) { if (x.parentNode) x.parentNode.removeChild(x); x.parentNode = this; this.childNodes.splice(this.childNodes.indexOf(ref), 0, x); }
    return n;
  }
  removeChild(n) { const i = this.childNodes.indexOf(n); if (i >= 0) { this.childNodes.splice(i, 1); n.parentNode = null; } return n; }
  append(...ns) { for (const n of ns) this.appendChild(typeof n === "string" ? new __Text(__escText(n)) : n); }
  prepend(...ns) { const first = this.firstChild; for (const n of ns) this.insertBefore(typeof n === "string" ? new __Text(__escText(n)) : n, first); }
  replaceChildren(...ns) { for (const c of this.childNodes) c.parentNode = null; this.childNodes = []; this.append(...ns); }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  replaceWith(...ns) { const p = this.parentNode; if (!p) return; for (const n of ns) p.insertBefore(typeof n === "string" ? new __Text(__escText(n)) : n, this); p.removeChild(this); }
  insertAdjacentHTML(where, h) {
    const ns = __parse(String(h)), w = String(where).toLowerCase();
    if (w === "beforeend") ns.forEach((n) => this.appendChild(n));
    else if (w === "afterbegin") { const f = this.firstChild; ns.forEach((n) => this.insertBefore(n, f)); }
    else if (w === "beforebegin") ns.forEach((n) => this.parentNode.insertBefore(n, this));
    else if (w === "afterend") { const nx = this.nextSibling; ns.forEach((n) => this.parentNode.insertBefore(n, nx)); }
  }
  contains(n) { for (let x = n; x; x = x.parentNode) if (x === this) return true; return false; }
  *_walk() { for (const c of this.childNodes) if (c.nodeType === 1) { yield c; yield* c._walk(); } }
  querySelectorAll(sel) { const m = __compile(sel); return [...this._walk()].filter((e) => m(e)); }
  querySelector(sel) { const m = __compile(sel); for (const e of this._walk()) if (m(e)) return e; return null; }
  getElementsByTagName(t) { return this.querySelectorAll(t); }
  getElementsByClassName(c) { return this.querySelectorAll(c.trim().split(/\s+/).map((x) => "." + x).join("")); }
  matches(sel) { return __compile(sel)(this); }
  closest(sel) { const m = __compile(sel); for (let e = this; e && e.nodeType === 1; e = e.parentNode) if (m(e)) return e; return null; }
  addEventListener(type, fn, opts) { if (!fn) return; const cap = opts === true || !!(opts && opts.capture);
    (this._ls[type] = this._ls[type] || []).push({ fn, cap }); }
  removeEventListener(type, fn) { this._ls[type] = (this._ls[type] || []).filter((l) => l.fn !== fn); }
  dispatchEvent(ev) { __dispatch(this, ev); return !ev.defaultPrevented; }
  click() { __click(this); }
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = document.body; }
  getBoundingClientRect() { return { left: 0, top: 0, right: __W, bottom: 0, width: __W, height: 0, x: 0, y: 0 }; }
  get clientWidth() { return __W; } get offsetWidth() { return __W; } get clientHeight() { return 0; } get offsetHeight() { return 0; }
  get scrollHeight() { return 0; } get scrollWidth() { return __W; }
  scrollIntoView() {} animate() { return { finished: Promise.resolve(), cancel() {}, onfinish: null }; } getAnimations() { return []; }
}
function __ser(n) {
  if (n.nodeType === 3) return n.raw;
  if (n.nodeType === 11) return n.childNodes.map(__ser).join("");
  const attrs = [...n._a].map(([k, v]) => " " + k + '="' + __escAttr(v) + '"').join("");
  return "<" + n.localName + attrs + ">" + (__VOID.has(n.localName) ? "" : n.childNodes.map(__ser).join("") + "</" + n.localName + ">");
}
const __TOK = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>|[^<]+|</g;
const __ATTR = /([^\s=\/"'>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
function __parse(h) {
  const frag = new __El("#fragment"); frag.nodeType = 11;
  const stack = [frag], re = new RegExp(__TOK.source, "g");
  let m;
  while ((m = re.exec(h))) {
    const top = stack[stack.length - 1];
    if (m[0].startsWith("<!--")) continue;
    if (m[1]) {                                     // a closing tag closes up to its own element; a stray one is ignored
      const name = m[1].toLowerCase();
      for (let k = stack.length - 1; k > 0; k--) if (stack[k].localName === name) { stack.length = k; break; }
      continue;
    }
    if (m[2]) {
      const name = m[2].toLowerCase(), raw = m[3] || "", attrs = [], ar = new RegExp(__ATTR.source, "g");
      let a;
      while ((a = ar.exec(raw))) { const k = a[1].toLowerCase(); if (!attrs.some(([x]) => x === k)) attrs.push([k, __decode(a[2] ?? a[3] ?? a[4] ?? "")]); }
      const el = new __El(name, attrs);
      top.appendChild(el);
      if (name === "details" && el.hasAttribute("open")) __detailsChanged(el);   // a browser fires toggle for <details open> too
      if (!__VOID.has(name) && !/\/\s*$/.test(raw)) stack.push(el);
      continue;
    }
    top.appendChild(new __Text(m[0]));
  }
  return [...frag.childNodes];
}

// ---- selectors: lists, compounds (tag, #id, .class, [attr op value], :not/:is/:where/:first-child/:last-child), combinators
const __cache = new Map();
const __unesc = (s) => s.replace(/\\([0-9a-fA-F]{1,6}\s?|[\s\S])/g, (m, c) => (/^[0-9a-fA-F]/.test(c) && c.trim().length ? String.fromCodePoint(parseInt(c, 16)) : c));
const __IDENT = /^(?:\\[0-9a-fA-F]{1,6}\s?|\\[\s\S]|[\w-]|[^\x00-\x7f])+/;
const __bad = (s) => { throw new Error("the stand-in DOM can't read the selector " + JSON.stringify(s)); };
function __split(s, sep) {
  const out = []; let depth = 0, q = null, cur = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "\\") { cur += c + (s[i + 1] || ""); i++; continue; }
    if (q) { if (c === q) q = null; cur += c; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === "(" || c === "[") depth++;
    else if (c === ")" || c === "]") depth--;
    else if (c === sep && depth === 0) { out.push(cur); cur = ""; continue; }
    cur += c;
  }
  out.push(cur);
  return out;
}
function __close(s, i, open, shut) {
  let depth = 0, q = null;
  for (let j = i; j < s.length; j++) {
    const c = s[j];
    if (c === "\\") { j++; continue; }
    if (q) { if (c === q) q = null; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === open) depth++;
    else if (c === shut && --depth === 0) return j;
  }
  __bad(s);
}
function __ident(s, i) { const m = __IDENT.exec(s.slice(i)); if (!m) __bad(s); return [__unesc(m[0]), i + m[0].length]; }
function __attrTest(src, whole) {
  const m = /^\s*((?:\\[\s\S]|[\w-])+)\s*(?:([~|^$*]?=)\s*(?:"((?:\\[\s\S]|[^"\\])*)"|'((?:\\[\s\S]|[^'\\])*)'|((?:\\[\s\S]|[^\s\]])+))\s*([iIsS])?)?\s*$/.exec(src);
  if (!m) __bad(whole);
  const name = __unesc(m[1]).toLowerCase(), op = m[2], ci = (m[6] || "").toLowerCase() === "i";
  let want = op ? __unesc(m[3] ?? m[4] ?? m[5]) : null;
  if (ci && want != null) want = want.toLowerCase();
  return (el) => {
    if (!el.hasAttribute(name)) return false;
    if (!op) return true;
    let v = el.getAttribute(name); if (ci) v = v.toLowerCase();
    if (op === "=") return v === want;
    if (op === "~=") return v.split(/\s+/).includes(want);
    if (op === "|=") return v === want || v.startsWith(want + "-");
    if (op === "^=") return want !== "" && v.startsWith(want);
    if (op === "$=") return want !== "" && v.endsWith(want);
    return want !== "" && v.includes(want);
  };
}
function __pseudo(name, arg, whole) {
  if (name === "not") { const f = __compile(arg); return (el) => !f(el); }
  if (name === "is" || name === "where") { const f = __compile(arg); return f; }
  if (name === "first-child") return (el) => !el.previousElementSibling;
  if (name === "last-child") return (el) => !el.nextElementSibling;
  if (name === "only-child") return (el) => !el.previousElementSibling && !el.nextElementSibling;
  if (name === "empty") return (el) => el.childNodes.length === 0;
  if (name === "checked") return (el) => el.hasAttribute("checked");
  if (name === "disabled") return (el) => el.hasAttribute("disabled");
  return __bad(whole);
}
function __compound(s, i, whole) {
  const tests = [], st = i;
  if (s[i] === "*") i++;
  else if (s[i] && /[\w\\-]/.test(s[i])) { let t; [t, i] = __ident(s, i); t = t.toLowerCase(); tests.push((el) => el.localName === t); }
  for (;;) {
    const c = s[i];
    if (c === "#") { let v; [v, i] = __ident(s, i + 1); tests.push((el) => el.getAttribute("id") === v); }
    else if (c === ".") { let v; [v, i] = __ident(s, i + 1); tests.push((el) => el.className.split(/\s+/).includes(v)); }
    else if (c === "[") { const e = __close(s, i, "[", "]"); tests.push(__attrTest(s.slice(i + 1, e), whole)); i = e + 1; }
    else if (c === ":") {
      if (s[i + 1] === ":") __bad(whole);
      let name; [name, i] = __ident(s, i + 1);
      let arg = null;
      if (s[i] === "(") { const e = __close(s, i, "(", ")"); arg = s.slice(i + 1, e); i = e + 1; }
      tests.push(__pseudo(name.toLowerCase(), arg, whole));
    } else break;
  }
  if (i === st) __bad(whole);
  return [(el) => tests.every((t) => t(el)), i];
}
function __complex(s) {
  const parts = []; let i = 0;
  const ws = () => { const a = i; while (i < s.length && /\s/.test(s[i])) i++; return i > a; };
  ws();
  while (i < s.length) {
    const [f, ni] = __compound(s, i, s); i = ni; parts.push(f);
    const gap = ws();
    if (i >= s.length) break;
    if (">+~".includes(s[i])) { parts.push(s[i]); i++; ws(); }
    else if (gap) parts.push(" ");
    else __bad(s);
  }
  if (!parts.length) __bad(s);
  const match = (el, k) => {
    if (!parts[k](el)) return false;
    if (k === 0) return true;
    const comb = parts[k - 1], j = k - 2;
    if (comb === ">") { const p = el.parentElement; return !!p && match(p, j); }
    if (comb === " ") { for (let p = el.parentElement; p; p = p.parentElement) if (match(p, j)) return true; return false; }
    if (comb === "+") { const p = el.previousElementSibling; return !!p && match(p, j); }
    for (let p = el.previousElementSibling; p; p = p.previousElementSibling) if (match(p, j)) return true;
    return false;
  };
  return (el) => match(el, parts.length - 1);
}
function __compile(sel) {
  sel = String(sel);
  if (!__cache.has(sel)) { const fs = __split(sel, ",").map((x) => __complex(x.trim())); __cache.set(sel, (el) => fs.some((f) => f(el))); }
  return __cache.get(sel);
}

// ---- events
function __event(type, bubbles) {
  return { type, bubbles, cancelable: true, defaultPrevented: false, target: null, currentTarget: null, button: 0, detail: 1,
    _stop: false, _stopNow: false, _path: [], preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this._stop = true; },
    stopImmediatePropagation() { this._stop = this._stopNow = true; }, composedPath() { return this._path; } };
}
function __dispatch(target, ev) {
  const path = [];
  for (let x = target; x; x = x.parentNode) path.push(x);
  path.push(window);
  ev.target = target; ev._path = path;
  const call = (node, phase) => {                   // phase: "capture", "target" or "bubble"
    for (const l of [...((node._ls || {})[ev.type] || [])]) {
      if ((phase === "capture" && !l.cap) || (phase === "bubble" && l.cap)) continue;
      ev.currentTarget = node; __safe(() => l.fn.call(node, ev));
      if (ev._stopNow) return;
    }
    const prop = phase !== "capture" && node !== window ? node["on" + ev.type] : null;
    if (typeof prop === "function") { ev.currentTarget = node; __safe(() => prop.call(node, ev)); }
  };
  for (let i = path.length - 1; i > 0; i--) { call(path[i], "capture"); if (ev._stop) return; }
  call(target, "target");
  if (ev._stop || !ev.bubbles) return;
  for (let i = 1; i < path.length; i++) { call(path[i], "bubble"); if (ev._stop) return; }
}
function __click(el) {                              // a click, then what the browser does with it: a summary opens its details
  const ev = __event("click", true);
  __dispatch(el, ev);
  const sum = !ev.defaultPrevented && el.closest("summary"), det = sum && sum.parentElement;
  if (det && det.localName === "details" && det.firstElementChild === sum) det.open = !det.open;
}

// ---- the page's world
const document = { nodeType: 9, _ls: {}, hidden: false, visibilityState: "visible", readyState: "complete", title: "", parentNode: null,
  addEventListener(type, fn, opts) { __El.prototype.addEventListener.call(this, type, fn, opts); },
  removeEventListener(type, fn) { __El.prototype.removeEventListener.call(this, type, fn); },
  dispatchEvent(ev) { __dispatch(this, ev); return !ev.defaultPrevented; },
  getElementById(id) { for (const e of this.documentElement._walk()) if (e.getAttribute("id") === String(id)) return e; return null; },
  querySelector(sel) { return this.documentElement.matches(sel) ? this.documentElement : this.documentElement.querySelector(sel); },
  querySelectorAll(sel) { return (this.documentElement.matches(sel) ? [this.documentElement] : []).concat(this.documentElement.querySelectorAll(sel)); },
  getElementsByTagName(t) { return this.querySelectorAll(t); },
  getElementsByClassName(c) { return this.documentElement.getElementsByClassName(c); },
  createElement(tag) { return new __El(tag); },
  createTextNode(t) { return new __Text(__escText(t)); },
  createDocumentFragment() { const f = new __El("#fragment"); f.nodeType = 11; return f; },
};
document.documentElement = new __El("html", [["lang", "en"]]);
document.documentElement.parentNode = document;
document.head = document.documentElement.appendChild(new __El("head"));
document.body = document.documentElement.appendChild(new __El("body"));
document.body.innerHTML = __I.body;
document.activeElement = document.body;
__tasks.length = 0;
globalThis.document = document;
globalThis.window = globalThis;
globalThis.self = globalThis;
window._ls = {};
window.addEventListener = (type, fn, opts) => __El.prototype.addEventListener.call(window, type, fn, opts);
window.removeEventListener = (type, fn) => __El.prototype.removeEventListener.call(window, type, fn);
window.dispatchEvent = (ev) => { __dispatch(window, ev); return true; };
globalThis.Node = __Node; globalThis.Element = __El; globalThis.HTMLElement = __El; globalThis.Text = __Text;
globalThis.Event = class { constructor(type, o) { Object.assign(this, __event(type, !!(o && o.bubbles))); } };
globalThis.CustomEvent = class extends globalThis.Event { constructor(type, o) { super(type, o); this.detail = o && o.detail; } };
globalThis.CSS = { escape: (s) => String(s).replace(/[^\w-]|^\d/g, (c) => "\\" + c), supports: () => true };
globalThis.innerWidth = 1280; globalThis.innerHeight = 900; globalThis.devicePixelRatio = 1; globalThis.scrollX = 0; globalThis.scrollY = 0;
globalThis.scrollTo = () => {}; globalThis.scrollBy = () => {};
globalThis.location = { href: "http://127.0.0.1:8000/", search: "", hash: "", pathname: "/", reload() {} };
globalThis.history = { replaceState() {}, pushState() {} };
globalThis.navigator = { userAgent: "node", language: "en-US" };
globalThis.matchMedia = (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
globalThis.getComputedStyle = () => ({ getPropertyValue: () => "" });
globalThis.localStorage = { getItem: (k) => (__store.has(String(k)) ? __store.get(String(k)) : null), setItem: (k, v) => { __store.set(String(k), String(v)); },
  removeItem: (k) => { __store.delete(String(k)); }, clear: () => __store.clear(), key: (i) => [...__store.keys()][i] ?? null, get length() { return __store.size; } };
globalThis.sessionStorage = { getItem: () => null, setItem() {}, removeItem() {}, clear() {} };
globalThis.performance = { now: () => __now - __I.now, mark() {}, measure() {} };
globalThis.structuredClone = (v) => JSON.parse(JSON.stringify(v));
globalThis.setInterval = (fn, ms, ...args) => { const id = ++__tid; const every = Math.max(0, +ms || 0); __timers.push({ id, fn, args, every, due: __now + every }); return id; };
globalThis.setTimeout = (fn, ms, ...args) => { const id = ++__tid; __timers.push({ id, fn, args, every: null, due: __now + Math.max(0, +ms || 0) }); return id; };
globalThis.clearInterval = globalThis.clearTimeout = (id) => { __timers = __timers.filter((t) => t.id !== id); };
globalThis.requestAnimationFrame = (fn) => { __raf.push(fn); return __raf.length; };
globalThis.cancelAnimationFrame = () => {};
globalThis.queueMicrotask = (fn) => { Promise.resolve().then(fn); };
globalThis.fetch = async (url) => {
  url = String(url); __log.push(url);
  const a = __answers[url] || __answers[url.split("?")[0]] || { status: 404, body: { error: "not found" } };
  const body = a.clock ? Object.assign({}, a.body, { now: __now / 1000 }) : a.body;    // the server's clock, now
  return { ok: a.status >= 200 && a.status < 300, status: a.status,
           json: async () => JSON.parse(JSON.stringify(body)), text: async () => JSON.stringify(body) };
};

// ---- running it: let promises, toggle events, animation frames and zero-delay timeouts finish; move the clock
async function __settle() {
  for (let round = 0; round < 40; round++) {
    for (let i = 0; i < 40; i++) await null;
    await new Promise((r) => __setImmediate(r));
    let did = false;
    for (const t of __tasks.splice(0)) { did = true; __safe(t); }
    for (const f of __raf.splice(0)) { did = true; __safe(() => f(__now)); }
    for (const t of __timers.filter((x) => x.every === null && x.due <= __now)) { did = true; __timers = __timers.filter((x) => x !== t); __safe(() => t.fn(...t.args)); }
    if (!did && round > 1) return;
  }
}
async function __advance(ms) {                      // the clock moves on; every timer that falls due runs, in order
  const end = __now + ms;
  for (;;) {
    const due = __timers.filter((t) => t.due <= end).sort((a, b) => a.due - b.due || a.id - b.id)[0];
    if (!due) break;
    __now = Math.max(__now, due.due);
    if (due.every === null) __timers = __timers.filter((t) => t !== due); else due.due += Math.max(1, due.every);
    __safe(() => due.fn(...due.args));
    await __settle();
  }
  __now = end;
  await __settle();
}
function __snap(extra) {
  const main = document.querySelector("main");
  return Object.assign({ fetches: __log.splice(0), errors: __errors.splice(0), main: main ? main.outerHTML : "",
                         bodyClass: document.body.className, store: Object.fromEntries(__store) }, extra || {});
}
async function __main() {
  const out = { loadError: __loadError, steps: [] };
  await __settle();                                 // its first /api/state and board reads come in
  await __advance(1000);                            // and a second passes: the board's 1-second redraw, with the account
  out.steps.push(__snap({ step: "loaded" }));
  for (const s of __I.steps) {
    let value = null, missing = null;
    if (s.answers) Object.assign(__answers, s.answers);
    if (s.store) for (const [k, v] of Object.entries(s.store)) (v === null ? __store.delete(k) : __store.set(k, v));
    if (s.click) {
      const el = document.querySelectorAll(s.click)[s.nth || 0];
      if (!el) missing = s.click; else { __click(el); await __settle(); }
    }
    if (s.advance) await __advance(s.advance);
    if (s.eval) {
      try { value = (0, eval)(s.eval); if (value && typeof value.then === "function") value = await value; value = JSON.parse(JSON.stringify(value ?? null)); }
      catch (e) { value = { __error: String(e) }; }
      await __settle();
    }
    out.steps.push(__snap({ step: s, missing, value }));
  }
  return JSON.stringify(out);
}
"""

RUNNER = """
const vm = require("vm"), fs = require("fs");
const p = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ console, URL, URLSearchParams, TextEncoder, TextDecoder, AbortController,
                               __in: p, __setImmediate: setImmediate, __loadError: null });
vm.runInContext(p.dom, ctx, { filename: "stand-in-dom.js" });
try { vm.runInContext(p.script, ctx, { filename: "dashboard.html" }); }
catch (e) { ctx.__loadError = String((e && e.stack) || e); }
process.on("unhandledRejection", (e) => { process.stderr.write("unhandled rejection: " + String((e && e.stack) || e)); process.exitCode = 1; });
vm.runInContext("__main()", ctx).then((out) => process.stdout.write(out),
  (e) => { process.stderr.write(String((e && e.stack) || e)); process.exitCode = 1; });
"""

_RUNS = {}


def run(steps=(), store=None, inputs=None, answers=None):
    """The Live tab opened with `store` as localStorage (strings, as the browser keeps them), then each step in turn: a
    click ({"click": selector}), the clock moving on ({"advance": ms}), new server answers, an expression evaluated in the
    page ({"eval": js}). [loaded, then one Page per step]."""
    if not NODE:
        pytest.skip("node isn't installed")
    g = inputs or golden()
    payload = json.dumps({"dom": DOM_JS, "script": '"use strict";' + SCRIPT, "body": BODY, "now": g["now"] * 1000,
                          "width": WIDTH, "store": store or {}, "answers": answers or routes(g), "steps": list(steps)},
                         sort_keys=True)
    if payload not in _RUNS:
        r = subprocess.run([NODE, "-e", RUNNER], input=payload, capture_output=True, text=True, encoding="utf-8",
                           timeout=120, env={**os.environ, "TZ": "America/New_York"})
        assert r.returncode == 0, r.stderr
        _RUNS[payload] = r.stdout
    out = json.loads(_RUNS[payload])
    assert not out["loadError"], f"dashboard.html's script didn't load:\n{out['loadError']}"
    pages = [Page(s) for s in out["steps"]]
    for i, p in enumerate(pages):
        what = "loading the page" if not i else f"step {i} {steps[i - 1]}"
        assert not p.errors, f"{what} threw:\n{p.errors[0]}"
        assert not p.missing, f"{what}: nothing on the page matches {p.missing!r}"
    return pages


def js(expr, store=None):
    """What `expr` evaluates to in the loaded page (its globals: FOLDS, foldOpen, fold, ...)."""
    v = run([{"eval": expr}], store=store)[-1].value
    assert not (isinstance(v, dict) and "__error" in v), f"{expr} failed in the page: {v and v['__error']}"
    return v


# ------------------------------------------------------------------ reading what the page holds
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class El:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, attrs, parent, []

    def els(self):
        for k in self.kids:
            if isinstance(k, El):
                yield k
                yield from k.els()

    def children(self):
        return [k for k in self.kids if isinstance(k, El)]

    def has_class(self, c):
        return c in self.attrs.get("class", "").split()

    def texts(self):
        for k in self.kids:
            if isinstance(k, str):
                yield k
            else:
                yield from k.texts()

    def text(self):
        """What it reads as, each tag a word break, whitespace collapsed."""
        return " ".join(" ".join(self.texts()).split())

    def inside(self, test):
        p = self.parent
        while p is not None:
            if test(p):
                return True
            p = p.parent
        return False


class Tree(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = El("#root", {}, None)
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        el = El(tag, {k: "" if v is None else v for k, v in attrs}, self.cur)
        self.cur.kids.append(el)
        if tag not in VOID:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(El(tag, {k: "" if v is None else v for k, v in attrs}, self.cur))

    def handle_endtag(self, tag):
        x = self.cur
        while x is not self.root and x.tag != tag:
            x = x.parent
        if x is not self.root:
            self.cur = x.parent

    def handle_data(self, data):
        self.cur.kids.append(data)


def live_els(node):
    """Every element of the Live tab: main without the two Research tabs and the live-bot sidebar beside them."""
    for k in node.children():
        if k.attrs.get("id") in NOT_LIVE:
            continue
        yield k
        yield from live_els(k)


def tokens(node):
    """The Live tab's text as a multiset of words, entities decoded, each tag a word break; the control labels the spec
    lets change (CONTROL) are left out, when they are a button's whole text."""
    out = Counter()

    def walk(n):
        for k in n.kids:
            if isinstance(k, str):
                out.update(k.split())
            elif k.attrs.get("id") in NOT_LIVE:
                continue
            elif k.tag == "button" and CONTROL.fullmatch(k.text()):
                continue
            else:
                walk(k)
    walk(node)
    return out


class Page:
    """One moment of the page: its <main> as the browser holds it, what it fetched since the last step, localStorage."""

    def __init__(self, s):
        self.fetches, self.errors, self.store = s["fetches"], s["errors"], s["store"]
        self.value, self.missing, self.body_class = s.get("value"), s.get("missing"), s.get("bodyClass")
        self.markup = s["main"]
        self._main = None

    @property
    def main(self):
        if self._main is None:
            self._main = Tree(self.markup).root
        return self._main

    def live(self):
        return list(live_els(self.main))

    def by_id(self, id_):
        hits = [e for e in self.main.els() if e.attrs.get("id") == id_]
        assert hits, f"nothing on the page has id={id_!r}"
        return hits[0]

    def fold_keys(self):
        return [e.attrs["data-fold-key"] for e in self.live() if "data-fold-key" in e.attrs]

    def fold(self, key):
        secs = [e for e in self.live() if e.attrs.get("data-fold-key") == key]
        assert len(secs) == 1, f'expected one fold data-fold-key="{key}" on the Live tab, found {len(secs)}; its folds: {self.fold_keys()}'
        sec = secs[0]
        heads = [e for e in sec.children() if e.has_class("fold-h")]
        assert len(heads) == 1, f'the "{key}" fold has no <div class="fold-h"> header of its own'
        buttons = [e for e in heads[0].els() if e.tag == "button" and e.attrs.get("data-fold") == key]
        assert len(buttons) == 1, f'the "{key}" fold\'s header has no <button data-fold="{key}">'
        bodies = [e for e in sec.children() if e.has_class("fold-body")]
        assert len(bodies) == 1, f'the "{key}" fold has no <div class="fold-body"> body of its own'
        metas = [e for e in heads[0].els() if e.tag == "span" and e.has_class("fold-m")]
        button, body = buttons[0], bodies[0]
        return types.SimpleNamespace(
            section=sec, head=heads[0], button=button, body=body, meta=" ".join(m.text() for m in metas),
            title=button.text(), open=sec.attrs.get("data-open"), expanded=button.attrs.get("aria-expanded"),
            hidden="hidden" in body.attrs, shown=sec.attrs.get("data-open") == "true")

    def is_open(self, key):
        """Whether a fold is open, after checking its section, button and body all agree."""
        f = self.fold(key)
        assert f.open in ("true", "false"), f'the "{key}" fold\'s data-open is {f.open!r}'
        assert (f.open, f.expanded, f.hidden) in (("true", "true", False), ("false", "false", True)), \
            f'the "{key}" fold disagrees with itself: data-open={f.open}, aria-expanded={f.expanded}, hidden={f.hidden}'
        return f.open == "true"

    def folds_buttons(self):
        return [e for e in self.live() if e.tag == "button" and "data-folds" in e.attrs]

    def folds_button(self):
        hits = self.folds_buttons()
        assert len(hits) == 1, f"expected one Open all / Close all button (data-folds) on the Live tab, found {len(hits)}"
        return hits[0].attrs["data-folds"], hits[0].text(), hits[0]

    def details(self):
        """The Details rows: {id: open?}."""
        return {e.attrs["data-sec"]: "open" in e.attrs for e in self.live() if e.tag == "details" and "data-sec" in e.attrs}

    def saved(self, key="folds"):
        raw = self.store.get(key)
        assert raw is not None, f'nothing saved under "{key}"'
        return json.loads(raw)


def click(selector, nth=0):
    return {"click": selector, "nth": nth}


def fold_button(key):
    return click(f'button[data-fold="{key}"]')


FOLDS_BUTTON = click("main [data-folds]")
POLL = {"advance": 5000}              # the page's 5-second refresh (and five of the board's 1-second redraws)


def headers():
    """What today's section headers said beside their titles (saved with the baseline)."""
    return golden()["headers"]


# ------------------------------------------------------------------ the shared helper: FOLDS, foldOpen, storage
@needs_node
def test_folds_names_every_live_and_live_research_fold_with_its_default():
    folds = js("FOLDS")
    assert isinstance(folds, dict), "FOLDS isn't an object"
    assert "side" not in folds, "the live-bot sidebar is gone from the research tabs, so there is no side fold"
    assert folds == {**LIVE_FOLDS, **LR_FOLDS}
    assert all(re.fullmatch(r"[a-z0-9.-]+", k) for k in folds), "fold keys hold only a-z, 0-9, dots and dashes"


@needs_node
def test_with_nothing_saved_every_fold_takes_its_default():
    keys = [*LIVE_FOLDS, *LR_FOLDS]
    got = js(f"Object.fromEntries({json.dumps(keys)}.map((k) => [k, foldOpen(k)]))")
    assert got == {**LIVE_FOLDS, **LR_FOLDS}


@needs_node
def test_a_saved_choice_beats_the_default_and_the_rest_keep_theirs():
    saved = {"live.positions": False, "live.orders": True, "lr.terms": True}
    got = js(f"Object.fromEntries({json.dumps([*LIVE_FOLDS, 'lr.terms', 'lr.shadow'])}.map((k) => [k, foldOpen(k)]))",
             store={"folds": json.dumps(saved)})
    assert got == {**LIVE_FOLDS, "live.positions": False, "live.orders": True, "lr.terms": True, "lr.shadow": True}


@needs_node
@pytest.mark.parametrize("raw", ["{not json", "[true, false]", '"live.orders"', "5", "true", "null", ""],
                         ids=["bad-json", "a-list", "a-string", "a-number", "a-boolean", "null", "empty"])
def test_a_saved_value_that_isnt_an_object_is_ignored(raw):
    got = js(f"Object.fromEntries({json.dumps([*LIVE_FOLDS, 'lr.shadow', 'lr.terms'])}.map((k) => [k, foldOpen(k)]))", store={"folds": raw})
    assert got == {**LIVE_FOLDS, "lr.shadow": True, "lr.terms": False}


@needs_node
def test_a_saved_choice_that_isnt_true_or_false_is_ignored_for_that_key():
    saved = {"live.orders": "yes", "live.positions": 0, "live.board": None, "live.details": "false", "live.method": True}
    got = js(f"Object.fromEntries({json.dumps(list(LIVE_FOLDS))}.map((k) => [k, foldOpen(k)]))", store={"folds": json.dumps(saved)})
    assert got == {**LIVE_FOLDS, "live.method": True}


# ------------------------------------------------------------------ the shared helper: fold()'s markup
def parse_one(markup):
    """The one element `markup` is."""
    root = Tree(markup).root
    assert len(root.children()) == 1 and not "".join(k for k in root.kids if isinstance(k, str)).strip(), \
        f"expected one element, got {markup[:200]!r}"
    return root.children()[0]


def check_fold_markup(markup, key, title, body, meta, cls, is_open):
    sec = parse_one(markup)
    want_cls = "fold" + (" " + cls if cls else "")
    assert sec.tag == "section" and sec.attrs.get("class") == want_cls, f"the outer element is <{sec.tag} class={sec.attrs.get('class')!r}>"
    assert sec.attrs.get("data-fold-key") == key and sec.attrs.get("data-open") == str(is_open).lower()
    head, fbody = sec.children()[0], sec.children()[-1]
    assert len(sec.children()) == 2, "a fold is its header, then its body"
    assert head.tag == "div" and head.attrs.get("class") == "fold-h"
    h2 = head.children()[0]
    assert h2.tag == "h2" and h2.attrs.get("class") == "fold-t", "the header starts with <h2 class=\"fold-t\">"
    assert len(h2.children()) == 1, "the heading holds the button alone"
    b = h2.children()[0]
    assert b.tag == "button" and b.attrs.get("type") == "button" and b.attrs.get("class") == "fold-b"
    assert b.attrs.get("data-fold") == key and b.attrs.get("aria-expanded") == str(is_open).lower()
    assert b.attrs.get("aria-controls") == "fold-" + key
    chev = b.kids[0]
    assert isinstance(chev, El) and chev.tag == "i" and chev.attrs == {"class": "chev", "aria-hidden": "true"} and not chev.kids, \
        "the button starts with <i class=\"chev\" aria-hidden=\"true\"></i>"
    assert b.text() == title
    metas = [e for e in head.children() if e.tag == "span" and e.has_class("fold-m")]
    if meta:
        assert len(metas) == 1 and head.children().index(metas[0]) > 0, "the meta follows the heading, inside the header"
        assert not metas[0].inside(lambda p: p.tag == "button"), "the meta sits outside the button"
        assert metas[0].text() == " ".join(htmllib.unescape(meta).split()), f"the meta reads {metas[0].text()!r}"
    else:
        assert not metas, "no meta, no empty <span class=\"fold-m\">"
    assert fbody.tag == "div" and fbody.attrs.get("class") == "fold-body" and fbody.attrs.get("id") == "fold-" + key
    assert ("hidden" in fbody.attrs) is (not is_open)
    assert body in markup and markup.index(body) > markup.index("fold-body"), "the body goes in as it came, already escaped"


@needs_node
@pytest.mark.parametrize("key, is_open", [("live.positions", True), ("live.orders", False)])
def test_fold_draws_the_markup_the_spec_pins(key, is_open):
    body = '<p class="x">Body &amp; more <b>12</b></p>'
    markup = js(f"fold({json.dumps(key)}, 'Some title', {json.dumps(body)}, '3 of 4 &amp; more', 'wide')")
    check_fold_markup(markup, key, "Some title", body, "3 of 4 &amp; more", "wide", is_open)


@needs_node
def test_fold_without_a_meta_or_a_class():
    markup = js("fold('live.method', 'How it trades', '<ul><li>a</li></ul>')")
    check_fold_markup(markup, "live.method", "How it trades", "<ul><li>a</li></ul>", "", "", False)


@needs_node
def test_fold_follows_the_saved_choice():
    store = {"folds": json.dumps({"live.positions": False, "live.orders": True})}
    check_fold_markup(js("fold('live.positions', 'P', '<i>b</i>', 'm')", store=store), "live.positions", "P", "<i>b</i>", "m", "", False)
    check_fold_markup(js("fold('live.orders', 'O', '<i>b</i>', 'm')", store=store), "live.orders", "O", "<i>b</i>", "m", "", True)


@needs_node
@pytest.mark.parametrize("keys, saved, label", [
    (["live.positions", "live.board"], {}, "Close all"),                                    # both open by default
    (["live.positions", "live.orders"], {}, "Open all"),                                    # orders is folded
    (["live.positions", "live.orders"], {"live.orders": True}, "Close all"),
    (list(LIVE_FOLDS), {k: True for k in LIVE_FOLDS}, "Close all"),
    (list(LIVE_FOLDS), {**{k: True for k in LIVE_FOLDS}, "live.details": False}, "Open all"),
])
def test_folds_button_reads_open_all_while_any_of_its_folds_is_closed(keys, saved, label):
    b = parse_one(js(f"foldsButton({json.dumps(keys)})", store={"folds": json.dumps(saved)}))
    assert b.tag == "button" and b.attrs.get("type") == "button"
    assert (b.attrs.get("data-folds"), b.text()) == (("open", "Open all") if label == "Open all" else ("close", "Close all"))


# ------------------------------------------------------------------ the Live tab's sections
@needs_node
def test_the_live_tab_has_five_folds_in_page_order():
    page = run()[0]
    assert page.fold_keys() == list(LIVE_FOLDS)
    for key, title in TITLES.items():
        assert page.fold(key).title.startswith(title), f'the "{key}" fold is titled {page.fold(key).title!r}'


@needs_node
def test_at_first_positions_board_and_details_are_open_and_orders_and_how_it_trades_closed():
    page = run()[0]
    assert {k: page.is_open(k) for k in LIVE_FOLDS} == LIVE_FOLDS


@needs_node
def test_each_fold_is_labelled_for_its_body():
    page = run()[0]
    ids = [e.attrs["id"] for e in page.main.els() if "id" in e.attrs]
    for key in LIVE_FOLDS:
        f = page.fold(key)
        assert f.button.attrs.get("aria-controls") == f.body.attrs.get("id") == "fold-" + key
        assert ids.count("fold-" + key) == 1


@needs_node
def test_folded_the_headers_still_say_each_sections_key_number():
    """Every fold closed: the counts and the lines beside today's titles are still in view, in the headers."""
    page = run(store=ALL_CLOSED)[0]
    for key, h in headers().items():
        f = page.fold(key)
        assert not page.is_open(key)
        if h["count"] is not None:
            assert h["count"] in f.head.text().split(), f'the "{key}" header lost its count {h["count"]}: {f.head.text()!r}'
        assert h["meta"] in f.head.text(), f'the "{key}" header lost {h["meta"]!r}: {f.head.text()!r}'
    for key in ("live.board", "live.orders", "live.method"):       # the lines beside the title are the fold's meta
        assert headers()[key]["meta"] in page.fold(key).meta, f'"{headers()[key]["meta"]}" isn\'t in the "{key}" fold\'s meta'


@needs_node
def test_a_folded_body_is_hidden_but_still_holds_everything():
    page = run(store=ALL_CLOSED)[0]
    bodies = {k: page.fold(k).body.text() for k in LIVE_FOLDS}
    assert all(page.fold(k).hidden for k in LIVE_FOLDS)
    assert "settles 3:00 PM" in bodies["live.positions"].replace(" ", " ") and "BTC 15 min" in bodies["live.positions"]
    assert all(m in bodies["live.board"] for m in ("BTC", "ETH", "GOLD", "WTI", "Favorite ↓", "In range"))
    assert all(x in bodies["live.orders"] for x in ("Placed", "Asked", "Filled", "Result", "insufficient balance", "no answer from Kalshi"))
    assert all(x in bodies["live.method"] for x in ("What it buys", "How much", "How it orders", "When it stops"))
    assert all(x in bodies["live.details"] for x in ("Numbers", "History", "Stop-losses", "Bot settings", "Decisions", "Errors"))


@needs_node
def test_the_hero_and_the_chart_dont_fold():
    page = run(store=ALL_CLOSED)[0]
    for id_ in ("hero", "chartPanel"):
        el = page.by_id(id_)
        assert not any("data-fold" in e.attrs or "data-fold-key" in e.attrs or e.has_class("fold") for e in [el, *el.els()]), id_
        assert not el.inside(lambda p: p.has_class("fold") or "data-fold-key" in p.attrs), f"#{id_} sits inside a fold"
        assert "hidden" not in el.attrs, f"#{id_} is hidden on the Live tab"
    opts = page.by_id("chartOpts")
    assert opts.tag == "button" and opts.text() == "Chart options"     # the chart keeps its own toggle


@needs_node
def test_details_keeps_its_rows_and_loses_its_expand_all_button():
    page = run()[0]
    body = page.fold("live.details").body
    rows = [e for e in body.els() if e.tag == "details"]
    assert [e.attrs.get("data-sec") for e in rows] == DETAILS
    assert all(e.has_class("acc") and e.children()[0].tag == "summary" for e in rows)   # still one-line rows that open on tap
    assert not [e for e in page.live() if "data-expand" in e.attrs], "the Details \"Expand all\" button is still there"
    words = " ".join(e.text() for e in page.live() if e.tag == "button")
    assert "Expand all" not in words and "Collapse all" not in words


@needs_node
def test_the_live_tab_has_one_open_all_button_and_it_is_always_in_view():
    page = run()[0]
    action, label, b = page.folds_button()
    assert (action, label) == ("open", "Open all")                # orders and how it trades start folded
    assert b.attrs.get("type") == "button"
    assert not b.inside(lambda p: p.has_class("fold-body")), "the Open all button is inside a fold's body"


@needs_node
def test_with_every_fold_saved_open_it_reads_close_all():
    action, label, _ = run(store={"folds": json.dumps({k: True for k in LIVE_FOLDS})})[0].folds_button()
    assert (action, label) == ("close", "Close all")


# ------------------------------------------------------------------ clicking a fold
@needs_node
@pytest.mark.parametrize("key", list(LIVE_FOLDS))
def test_a_click_flips_a_fold_in_place_saves_it_and_fetches_nothing(key):
    loaded, clicked = run([fold_button(key)])
    assert loaded.is_open(key) is LIVE_FOLDS[key]
    assert clicked.is_open(key) is (not LIVE_FOLDS[key]), "the click didn't flip the fold straight away"
    assert clicked.fetches == [], f"a fold click fetched {clicked.fetches}"
    assert clicked.saved().get(key) is (not LIVE_FOLDS[key])
    assert all(clicked.is_open(k) is v for k, v in LIVE_FOLDS.items() if k != key), "a click on one fold moved another"


@needs_node
def test_a_click_on_the_chevron_flips_it_too():
    """The browser hands the click to the innermost element: the chevron inside the button."""
    _, clicked = run([click('button[data-fold="live.method"] i.chev')])
    assert clicked.is_open("live.method") and clicked.saved()["live.method"] is True


@needs_node
def test_the_next_redraws_keep_the_choice():
    pages = run([fold_button("live.orders"), fold_button("live.positions"), fold_button("live.board"), POLL, POLL])
    for p in pages[3:]:
        assert (p.is_open("live.orders"), p.is_open("live.positions"), p.is_open("live.board")) == (True, False, False)
    assert any(u.startswith("/api/state") for u in pages[4].fetches), "the page didn't refresh during the 5 seconds"
    assert any(u.startswith("/api/research/live") for u in pages[4].fetches), "the board didn't redraw during the 5 seconds"


@needs_node
def test_a_second_click_flips_it_back_and_saves_that():
    *_, back = run([fold_button("live.orders"), fold_button("live.orders")])
    assert not back.is_open("live.orders") and back.saved()["live.orders"] is False


@needs_node
def test_saved_choices_open_the_page_as_they_were_left():
    page = run(store={"folds": json.dumps({"live.orders": True, "live.board": False})})[0]
    assert {k: page.is_open(k) for k in LIVE_FOLDS} == {**LIVE_FOLDS, "live.orders": True, "live.board": False}


@needs_node
@pytest.mark.parametrize("raw", ["[]", "5", "{not json", '"x"'], ids=["a-list", "a-number", "bad-json", "a-string"])
def test_after_a_bad_saved_value_a_click_still_works_and_saves_an_object(raw):
    loaded, clicked = run([fold_button("live.orders")], store={"folds": raw})
    assert not loaded.is_open("live.orders")
    assert clicked.is_open("live.orders")
    saved = clicked.saved()
    assert isinstance(saved, dict) and saved.get("live.orders") is True


@needs_node
def test_the_open_all_label_follows_single_clicks():
    _, one, both, closed_again = run([fold_button("live.orders"), fold_button("live.method"), fold_button("live.board")])
    assert one.folds_button()[:2] == ("open", "Open all")         # how it trades is still folded
    assert both.folds_button()[:2] == ("close", "Close all")      # now nothing is
    assert closed_again.folds_button()[:2] == ("open", "Open all")


# ------------------------------------------------------------------ Open all / Close all
@needs_node
def test_open_all_opens_every_fold_and_every_details_row():
    _, opened = run([FOLDS_BUTTON])
    assert all(opened.is_open(k) for k in LIVE_FOLDS)
    assert opened.details() == {k: True for k in DETAILS}
    assert {k: opened.saved().get(k) for k in LIVE_FOLDS} == {k: True for k in LIVE_FOLDS}
    assert sorted(opened.saved("open")) == sorted(DETAILS)         # the rows' own "open" storage, as today
    assert opened.folds_button()[:2] == ("close", "Close all")


@needs_node
def test_close_all_closes_every_fold_and_every_details_row():
    _, opened, closed = run([FOLDS_BUTTON, FOLDS_BUTTON])
    assert not any(closed.is_open(k) for k in LIVE_FOLDS)
    assert closed.details() == {k: False for k in DETAILS}
    assert {k: closed.saved().get(k) for k in LIVE_FOLDS} == {k: False for k in LIVE_FOLDS}
    assert closed.saved("open") == []
    assert closed.folds_button()[:2] == ("open", "Open all")


@needs_node
def test_open_all_and_close_all_survive_the_next_refresh():
    pages = run([FOLDS_BUTTON, POLL, FOLDS_BUTTON, POLL])
    assert all(pages[2].is_open(k) for k in LIVE_FOLDS) and all(pages[2].details().values())
    assert not any(pages[4].is_open(k) for k in LIVE_FOLDS) and not any(pages[4].details().values())


@needs_node
def test_the_live_tabs_open_all_leaves_live_researchs_choices_alone():
    store = {"folds": json.dumps({"lr.terms": True, "lr.shadow": False})}
    _, opened, closed = run([FOLDS_BUTTON, FOLDS_BUTTON], store=store)
    for p in (opened, closed):
        saved = p.saved()
        assert (saved.get("lr.terms"), saved.get("lr.shadow")) == (True, False)
        assert not [k for k in saved if k.startswith("lr.") and k not in ("lr.terms", "lr.shadow")], "it set Live Research's folds"


# ------------------------------------------------------------------ the Details rows, one by one, as today
@needs_node
def test_a_details_row_still_opens_on_its_own_and_stays_open():
    loaded, opened, later = run([click('details[data-sec="history"] > summary'), POLL])
    assert not any(loaded.details().values())
    for p in (opened, later):
        assert p.details() == {k: k == "history" for k in DETAILS}
    assert later.saved("open") == ["history"]


@needs_node
def test_rows_saved_open_today_still_open():
    page = run(store={"open": json.dumps(["stops", "errors"])})[0]
    assert page.details() == {k: k in ("stops", "errors") for k in DETAILS}


# ------------------------------------------------------------------ the board: a header that keeps up while folded
def board_later(g, now):
    """A second later the feed has moved on: a market more, polling instead of streaming."""
    hype = board_market("HYPE", "crypto", 0.92, 0.93, climb(0.88, 0.92))
    return {"/api/research/live": {"status": 200, "body": {"now": now, "stamp": 0, "live": board_feed(now, "poll", [hype])}}}


@needs_node
def test_the_boards_header_keeps_updating_while_it_is_folded():
    g = golden()
    later = g["now"] + 1 + 60                        # a minute on: minute 7 of the window
    page, moved = run([{"answers": board_later(g, later)}, {"advance": 60_000}],
                      store={"folds": json.dumps({"live.board": False})})[1:]
    assert not page.is_open("live.board") and not moved.is_open("live.board")
    assert headers()["live.board"]["meta"] in page.fold("live.board").meta   # before: 7 markets, streaming, minute 6
    f = moved.fold("live.board")
    assert "8" in f.head.text().split(), f"the folded board's header didn't update its count: {f.head.text()!r}"
    assert "Polling · minute 7 of 15" in f.meta, f"the folded board's header didn't update its status: {f.meta!r}"
    assert "HYPE" in f.body.text() and f.hidden, "the hidden board wasn't redrawn"


@needs_node
def test_a_board_folded_by_a_click_stays_folded_through_its_redraws():
    g = golden()
    pages = run([fold_button("live.board"), {"answers": board_later(g, g["now"] + 2)}, {"advance": 1000}, {"advance": 3000}])
    for p in pages[1:]:
        assert not p.is_open("live.board")
    assert "HYPE" in pages[-1].fold("live.board").body.text() and "Polling" in pages[-1].fold("live.board").meta


# ------------------------------------------------------------------ nothing is removed (section 2)
# The one move allowed since the baseline: the board's group tag went from each row to its
# group's header. The fixed data's five crypto rows each said "Crypto"; now the one header does (Metals and Energy have
# one row each, so no change there; the headers' counts add numbers, which is allowed). And one change of wording
# (the faster polling): the footer's "refreshes every 5 seconds" now reads "refreshes every second".
MOVED = Counter({"Crypto": 4, "seconds": 1})


def missing(page):
    """The words of today's Live tab that the page no longer holds (with how many are short), numbers first."""
    have, want = tokens(page.main), Counter(golden()["tokens"]) - MOVED
    short = {w: n - have[w] for w, n in want.items() if have[w] < n}
    return dict(sorted(short.items(), key=lambda x: (not re.search(r"\d", x[0]), x[0])))


STATES = {"defaults": {}, "every-fold-closed": ALL_CLOSED, "every-fold-open": ALL_OPEN}


@needs_node
@pytest.mark.parametrize("state", list(STATES))
def test_every_word_of_todays_live_tab_is_still_there(state):
    gone = missing(run(store=STATES[state])[0])
    assert not gone, f"{len(gone)} words of today's Live tab are gone or fewer ({state}): {list(gone.items())[:40]}"


@needs_node
@pytest.mark.parametrize("state", list(STATES))
def test_every_number_of_todays_live_tab_is_still_there_as_often(state):
    have, want = tokens(run(store=STATES[state])[0].main), golden()["tokens"]
    short = {w: (n, have[w]) for w, n in want.items() if re.search(r"\d", w) and have[w] < n}
    assert not short, f"numbers gone or shown fewer times ({state}), as {{number: (today, now)}}: {short}"


@needs_node
def test_after_open_all_and_close_all_nothing_is_gone_either():
    for p in run([FOLDS_BUTTON, FOLDS_BUTTON])[1:]:
        gone = missing(p)
        assert not gone, f"{len(gone)} words of today's Live tab are gone: {list(gone.items())[:40]}"


def test_the_baseline_is_todays_page_drawn_from_rich_data():
    """The saved words cover every section: a check that the baseline is the one the spec asks for, made once."""
    g = golden()
    words = Counter(g["tokens"])
    for w in ("Positions", "Live", "markets", "Orders", "How", "trades", "Details", "Numbers", "History", "Stop-losses",
              "Decisions", "BTC", "GOLD", "WTI", "insufficient", "Fed", "Next", "entry", "In", "range"):
        assert words[w], f"the baseline has no {w!r}"
    assert sum(n for w, n in words.items() if re.search(r"\d", w)) > 150, "the baseline holds few numbers"
    assert "Expand" not in words and "Collapse" not in words           # control labels are left out
    assert set(g["headers"]) == {"live.positions", "live.board", "live.orders", "live.method"}
    assert len(g["state"]["openBets"]) == 2 and len(g["state"]["orders"]) == 12 and g["state"]["kalshi"]["value"]


@needs_node
def test_todays_page_draws_the_details_rows_the_tests_expect():
    """Holds before and after the folds: the Details rows these tests open and close."""
    assert list(run()[0].details()) == DETAILS


# ------------------------------------------------------------------ writing the baseline (once, before the folds)
def todays_headers(page):
    """Today's section headers (div.block-h): the count beside each title and the line on its right."""
    out = {}
    for key, id_ in (("live.positions", "positions"), ("live.board", "board"), ("live.orders", "orders"), ("live.method", "method")):
        head = next(e for e in page.by_id(id_).els() if e.has_class("block-h"))
        h2 = next(e for e in head.els() if e.tag == "h2")
        count = next((e.text() for e in h2.els() if e.has_class("n")), None)
        meta = " ".join(e.text() for e in head.children() if e.tag != "h2")
        out[key] = {"count": count, "meta": meta}
    return out


@pytest.mark.skipif(not WRITE, reason="writes folds_baseline_live.json only with FOLDS_WRITE_BASELINE=1, from the page before the folds")
def test_write_the_baseline(home, monkeypatch):
    assert "function fold(" not in SCRIPT and "data-fold-key" not in SCRIPT, \
        "dashboard.html already has the folds: the baseline must come from the page before them"
    state = build_state(home, monkeypatch)
    inputs = {"now": CLOCK, "state": state, "board": board_feed(CLOCK)}
    page = run(inputs=inputs)[0]
    assert all(page.by_id(i).text() for i in ("positions", "board", "orders", "method", "more")), "a section drew nothing"
    out = {"about": "The Live tab's text as dashboard.html drew it before the folds, and the data "
                    "it was drawn from. Written once by test_folds_live.py with FOLDS_WRITE_BASELINE=1; never rewrite it "
                    "from a page that has the folds.",
           "dashboard.html md5": hashlib.md5(open(dashboard.PAGE, "rb").read()).hexdigest(),
           "now": CLOCK, "headers": todays_headers(page), "tokens": dict(sorted(tokens(page.main).items())),
           "state": state, "board": inputs["board"]}
    with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
