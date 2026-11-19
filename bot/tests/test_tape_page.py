"""The Tape page (SPEC_TAPE.md): a second dashboard page at /tape, in a dark trading-terminal layout.

Added Nov 6, 2026: the "Tape" mockup, built out as a real, working page. It shows what the classic page's Live/Paper tab shows, with the bot's "tape" as the main
event: every decision the bot logged and every bet that settled, newest first. The classic page at / stays as it was.

Three scripts draw it, loaded in this order: tape_fmt.js (the shared number and time formats, window.TapeFmt),
tape_panels.js (the left-hand tabs: live markets, orders, fill rate, by market, rules; window.TapePanels) and tape.js
(the strip of figures, the grid of every bet, the chart, the tape itself, the banners and the wiring; window.Tape).
Each must load in node with only `window = {}` defined, so these tests load all three in node's vm, the way the page
loads them, and hand the pure functions small hand-made replies shaped like /api/state and /api/research/live. They
check what the page says, not how it lays it out. The rest is read as text: the route and its files in dashboard.py,
tape.html's layout and look, and the rules every page here keeps (nothing loads from outside, halting takes two taps,
nothing on the page can resume the bot).

The node tests skip themselves without node. While a file doesn't exist yet, its tests fail plainly and say so.

    python -m pytest tests/test_tape_page.py -q
"""
import contextlib
import html
import itertools
import json
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

import pytest

from kalshi_bot.web import dashboard
from layout import STATIC

HERE = STATIC   # the dashboard's pages: dashboard.html, tape.html and their .js and .css
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")

SCRIPTS = ("tape_fmt.js", "tape_panels.js", "tape.js")       # tape.html's load order
STYLES = ("tape.css", "tape_panels.css")
OWNER = {"TapeFmt": "tape_fmt.js", "TapePanels": "tape_panels.js", "Tape": "tape.js"}
TAPE_FUNCTIONS = ("events", "filter", "feedHtml", "openHtml", "grid", "gridHtml", "strip", "countdown", "banners",
                  "chartHtml")
PANEL_FUNCTIONS = ("board", "boardStatus", "orders", "fills", "markets", "rules")


def own(name):
    """One of the page's own files beside dashboard.py: a plain failure, not a crash, while it doesn't exist yet."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        pytest.fail(f"{name} doesn't exist yet")
    return open(path, encoding="utf-8").read()


def code(js):
    """A script or stylesheet without its comments (block comments and whole-line // comments)."""
    return re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", js, flags=re.S), flags=re.M)


def norm(s):
    return re.sub(r"[\s\u00a0\u202f\u2009]+", " ", s)


def text(markup):
    """What the markup reads as: each tag a space, entities decoded, odd spaces made plain."""
    return norm(html.unescape(re.sub(r"<[^>]+>", " ", markup or ""))).strip()


def joined(markup):
    """The same with tags simply dropped, so "<b>+</b>20.9%" reads "+20.9%"."""
    return norm(html.unescape(re.sub(r"<[^>]+>", "", markup or ""))).strip()


def shows(markup, s):
    return norm(s) in text(markup) or norm(s) in joined(markup)


def esc(s):
    """TapeFmt.esc()."""
    return "".join({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}.get(c, c) for c in str(s))


# ------------------------------------------------------------------ data shaped like the server's
W0 = 1_794_004_200          # a window's start: Nov 6, 2026, 2:30 PM PT (22:30 UTC)
NOW = W0 + 600              # minute 10 of it: this window's bets are in
ET = timezone(timedelta(hours=-5))   # Kalshi names a window by its close, New York time (EST in November)
_ids = itertools.count(1)


def tk(sym, w):
    """The ticker of a market's window starting at w: KXBTC15M-26NOV061745-45."""
    close = datetime.fromtimestamp(w + 900, ET)
    return f"KX{sym}15M-{close.strftime('%y%b%d%H%M').upper()}-{close.strftime('%M')}"


def sym_of(ticker):
    return re.sub(r"15M$", "", re.sub(r"^KX", "", ticker.split("-")[0]))


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def money(v):
    return f"${v:,.2f}"


def bet(sym, w, status, side="yes", price=0.96, contracts=18, settled_after=27):
    """A row of state()'s recentBets (settled) or openBets (open, with its mark and value now)."""
    n = next(_ids)
    cost, fee = round(price * contracts, 2), 0.02
    pnl = round(contracts - cost - fee, 2) if status == "won" else -round(cost + fee, 2)
    b = {"id": n, "ticker": tk(sym, w), "series": f"KX{sym}15M", "window_open": float(w), "close_ts": float(w + 900),
         "side": side, "price": price, "contracts": float(contracts), "cost": cost, "fee": fee,
         "placed_ts": w + 480.005, "order_id": None, "client_order_id": f"c-{n}", "status": status,
         "result": None if status == "open" else side if status == "won" else ("no" if side == "yes" else "yes"),
         "payout": None if status == "open" else float(contracts) if status == "won" else 0.0,
         "pnl": None if status == "open" else pnl,
         "settled_ts": None if status == "open" else w + 900 + settled_after}
    if status == "open":
        b.update(mark=0.99, unrealized=round(contracts * 0.99 - cost - fee, 2))
    return b


def dec(sym, w, action, side, price, reason):
    """A row of state()'s decisions: every market at minute 8 of each window shares one time, as the bot logs them."""
    return {"ts": w + 480.0003, "ticker": tk(sym, w), "series": f"KX{sym}15M", "fav_side": side, "fav_price": price,
            "action": action, "reason": reason}


def order(sym, w, side="yes", price=0.96, asked=18, filled=18, error=None, result="won", pnl=0.5, at=0.32):
    """A row of state()'s orders (order_row() plus how its bet did)."""
    return {"ts": w + 480 + at, "ticker": tk(sym, w), "series": f"KX{sym}15M", "side": side, "price": price,
            "asked": float(asked), "filled": None if filled is None else float(filled), "error": error,
            "result": result, "pnl": pnl, "close_ts": None if filled is None else float(w + 900),
            "atAsk": None if filled is None else 40.0, "plusOne": None if filled is None else 5.0}


def series_row(sym, n, wins, pnl, staked):
    return {"series": f"KX{sym}15M", "n": n, "wins": wins, "pnl": pnl, "staked": staked}


ZERO = {"orders": 0, "asked": 0, "filled": 0, "none": 0}
LIMITS = {"betPct": 0.015, "windowPct": 0.1, "ordersPerWindow": 20, "ordersPerDay": 600, "minCash": 66.67,
          "dayDrop": 0.35, "halfStart": 0.5, "windowLosses": 8, "settleLag": 1800, "persist": 300, "orderErrors": 3,
          "minute": 8, "lo": 0.92, "hi": 0.999, "limitUp": 0.01, "shadowUp": 0.01, "grace": 45, "spreadMax": 0.02,
          "lateMid": 0.5, "jump": 0.1, "orderDeadline": 60, "bookMaxAge": 15, "restingEvery": 15, "orderConnect": 3.05,
          "orderAnswer": 5}


def paper_state(**over):
    """/api/state for a paper account, small: one bet open in this window, four settled
    in the three before it (one lost), a skip, a halt, an order that got nothing and the error it left, and the
    $1,000 simulation a paper account carries."""
    open_ = [bet("BTC", W0, "open", price=0.96, contracts=17)]
    settled = [bet("GOLD", W0 - 900, "lost", side="no", price=0.95, settled_after=31),      # newest settled first
               bet("BTC", W0 - 900, "won", price=0.959, contracts=17),
               bet("NATGAS", W0 - 1800, "won", price=0.99, contracts=17),
               bet("ETH", W0 - 2700, "won", price=0.97)]
    d = {
        "mode": "dry-prod", "modes": ["dry-prod"], "live": False, "env": "prod", "now": float(NOW),
        "clock": {"offset": 0.0, "synced": True, "checked": float(NOW)}, "heartbeat": NOW - 3.0,
        "restartBot": False, "halt": None,
        "blackout": {"what": "Fed decision", "from": W0 + 30 * 86400.0, "to": W0 + 30 * 86400 + 5400.0, "active": False},
        "start": 1000.0, "bankroll": 1204.74, "unrealized": sum(b["unrealized"] for b in open_), "haltBase": 1000.0,
        "limits": dict(LIMITS), "groups": ["crypto", "metals", "energy"],
        "openCost": sum(b["cost"] + b["fee"] for b in open_), "wins": 593, "losses": 7, "need": 0.9639,
        "winShare": 0.9875, "fees": 25.5, "maxDrop": 0.0152, "day": 131.86, "dayBets": 257,
        "staked": {"all": 8327.76, "bets": 600, "since": W0 - 2700 + 480.0, "day": 3829.01, "settled": 8327.76,
                   "profit": 204.74},
        "nextBet": 17.8,
        "curve": [[W0 - 2700 + 480.0, 1000.0], [W0 - 1800 + 27.0, 1204.31], [W0 - 900 + 27.0, 1204.46],
                  [W0 + 27.0, 1221.86], [W0 + 31.0, 1204.74]],
        "openBets": open_,
        "recentBets": settled,
        "bySeries": sorted([series_row("GOLD", 12, 11, -9.80, 200.0), series_row("SOL", 20, 19, -2.10, 330.0),
                            series_row("ETH", 30, 30, 4.10, 500.0), series_row("NATGAS", 9, 9, 1.35, 150.0),
                            series_row("BTC", 25, 25, 6.75, 420.0)], key=lambda s: s["pnl"]),
        "byPrice": [{"key": "92-94", "label": "92–94¢", "n": 30, "wins": 29, "pnl": 10.2, "staked": 520.0},
                    {"key": "95-97", "label": "95–97¢", "n": 40, "wins": 39, "pnl": 6.1, "staked": 700.0},
                    {"key": "98-99", "label": "98–99¢", "n": 26, "wins": 26, "pnl": 4.0, "staked": 450.0}],
        "decisions": [   # newest first
            dec("SOL", W0, "skip", "yes", 0.61, "favorite at 61.0c is outside 92-99.9c"),
            dec("BTC", W0, "bet", "yes", 0.96, "would buy YES 17 at 96.0c ($16.32 a bet)"),
            dec("ETH", W0, "bet", "no", 0.97, "would buy NO 18 at 97.0c ($17.46 a bet)"),
            dec("GOLD", W0 - 900, "bet", "no", 0.95, "would buy NO 18 at 95.0c ($17.10 a bet)"),
            dec("BTC", W0 - 900, "bet", "yes", 0.959, "would buy YES 17 at 95.9c ($16.30 a bet)"),
            dec("NATGAS", W0 - 1800, "bet", "yes", 0.99, "would buy YES 17 at 99.0c ($16.83 a bet)"),
            dec("DOGE", W0 - 2700, "skip", "no", 0.97, "warning sign: its ask is 3.0c over its bid (2.0c or more)"),
            dec("ETH", W0 - 2700, "bet", "yes", 0.97, "would buy YES 18 at 97.0c ($17.46 a bet)"),
            dec("HYPE", W0 - 3600, "halted", "yes", 0.96, "halted: 3 orders failed in a row"),
        ],
        "orders": [      # newest first
            order("ETH", W0, side="no", price=0.97, asked=18, filled=None, error="market closed", result=None,
                  pnl=None, at=0.41),
            order("BTC", W0, price=0.96, asked=17, filled=17, result="open", pnl=None),
            order("GOLD", W0 - 900, side="no", price=0.95, asked=18, filled=18, result="lost", pnl=-17.12, at=0.41),
            order("BTC", W0 - 900, price=0.959, asked=17, filled=17, result="won", pnl=0.68),
            order("NATGAS", W0 - 1800, price=0.99, asked=17, filled=17, result="won", pnl=0.15),
            order("ETH", W0 - 2700, price=0.97, asked=18, filled=18, result="won", pnl=0.52),
        ],
        "fills": {"orders": 2, "asked": 35, "filled": 17, "none": 1},
        "fillsAll": {"orders": 6, "asked": 105, "filled": 87, "none": 1, "since": W0 - 2700 + 480.32},
        "fillsHour": {"orders": 2, "asked": 35, "filled": 17, "none": 1},
        "fillsBySize": [{"label": "11–20", "lo": 11, "hi": 20, "orders": 5, "asked": 87, "filled": 87, "none": 0}],
        "fillWindows": [[W0 - 2700, 1, 18, 18, 0], [W0 - 1800, 1, 17, 17, 0], [W0 - 900, 2, 35, 35, 0],
                        [W0, 2, 35, 17, 1]],
        "fillOff": [],
        "fillsFast": {"live": 1792011600, "before": dict(ZERO), "after": {"orders": 6, "asked": 105, "filled": 87,
                                                                          "none": 1}},
        "errors": [{"ts": W0 + 480.41, "ticker": tk("ETH", W0), "http_status": 409,
                    "response": '{"error": {"code": "market_closed", "message": "market closed"}}'}],
        "sim": {"start": 1000.0, "value": 2505.13, "ret": 1.50513, "bets": 26388, "wins": 25580, "maxDD": 0.252,
                "curve": [1000.0, 1000.0, 1180.5, 1640.2, 2210.9, 2505.13], "winRate": 0.96938, "need": 0.9647,
                "t0": "2025-12-10T00:00:00+00:00", "hours": 7945, "step": 6},
    }
    d.update(over)
    return d


def live_state(**over):
    """The same on a real-money account: Kalshi's own reading of it, and no simulation."""
    d = paper_state(mode="live-prod", modes=["live-prod"], live=True,
                    kalshi={"total": 1300.0, "crypto": 1290.0, "positions": 1, "held": 17.5, "value": 1317.5}, **over)
    del d["sim"]
    return d


def bm(sym, group, side, fav, label=None):
    """A market on the live board (/api/research/live's live.markets)."""
    bid, ask = (round(fav - 0.01, 2), fav) if side == "yes" else (round(1 - fav, 2), round(1 - fav + 0.01, 2))
    return {"ticker": tk(sym, W0), "series": f"KX{sym}15M", "group": group, "label": label or sym,
            "open": iso(W0), "close": iso(W0 + 900), "strike": 100.0, "status": "active", "yes_bid": bid,
            "yes_ask": ask, "last": bid, "bid_size": 100.0, "ask_size": 50.0, "volume": 1000.0, "oi": 500.0,
            "favSide": side, "favPrice": fav, "path": [[1, 0.5, 0.52], [2, bid, ask]], "book": None, "trades": None}


def board_reply(source="stream", age=2, markets=None):
    """/api/research/live: the live board, its heartbeat `age` seconds old."""
    ms = markets if markets is not None else [bm("BTC", "crypto", "yes", 0.95), bm("ETH", "crypto", "no", 0.97),
                                              bm("GOLD", "metals", "yes", 0.93), bm("WTI", "energy", "no", 0.62),
                                              bm("RACE", "coin race", "yes", 0.55, label="RACE1")]
    return {"now": float(NOW), "stamp": NOW - 86400.0,
            "live": {"heartbeat": iso(NOW - age), "source": source, "streamWhy": None, "band": [0.92, 0.999],
                     "groups": ["crypto", "metals", "energy", "coin race"], "markets": ms}}


# ------------------------------------------------------------------ the scripts, run in node
# The three files run in one vm context whose only global is `window = {}` (and console), in tape.html's order, each
# on its own as separate <script> tags would; then the test's body runs in the same context with Tape, TapePanels,
# TapeFmt and the data D (parsed inside the context, so its arrays and objects are the context's own).
RUNNER = r"""
const vm = require("vm"), fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const ctx = vm.createContext({ window: {}, console });
const out = { loaded: {}, missing: [], result: null, error: null };
for (const [name, path] of input.files) {
  try { vm.runInContext(fs.readFileSync(path, "utf8"), ctx, { filename: name }); out.loaded[name] = null; }
  catch (e) { out.loaded[name] = String((e && e.stack) || e); }
}
const W = vm.runInContext("window", ctx);
for (const need of input.needs) {
  const [obj, fn] = need.split(".");
  if (!W[obj] || (fn && typeof W[obj][fn] !== "function")) out.missing.push(need);
}
if (!out.missing.length) {
  try {
    const test = vm.runInContext("(function (Tape, TapePanels, TapeFmt, D) {\n" + input.body + "\n})", ctx, { filename: "the test" });
    const r = test(W.Tape, W.TapePanels, W.TapeFmt, vm.runInContext("JSON", ctx).parse(input.data));
    out.result = r === undefined ? null : r;
  } catch (e) { out.error = String((e && e.stack) || e); }
}
process.stdout.write(JSON.stringify(out));
"""


def run(body, data=None, needs=()):
    """Run `body` (a JS function body that returns something JSON can carry) with the three scripts loaded. `needs`
    names the functions it calls ("Tape.events"): one a script doesn't set yet is a plain failure."""
    if not NODE:
        pytest.skip("node isn't installed")
    want = ["tape_fmt.js"] + [OWNER[n.split(".")[0]] for n in needs]
    for name in SCRIPTS:
        if name in want:
            own(name)
    files = [[n, os.path.join(HERE, n)] for n in SCRIPTS if os.path.exists(os.path.join(HERE, n))]
    payload = {"files": files, "needs": list(needs), "body": body, "data": json.dumps(data)}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", timeout=60, env={**os.environ, "TZ": "America/Los_Angeles"})
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    broken = [f"{n} doesn't load in node with only `window = {{}}` defined: {' / '.join(e.splitlines()[:3])}"
              for n, e in out["loaded"].items() if e and n in want]
    if broken:
        pytest.fail("; ".join(broken))
    if out["missing"]:
        pytest.fail("; ".join(f"{OWNER[m.split('.')[0]]} doesn't set window.{m} yet" for m in out["missing"]))
    if out["error"]:
        pytest.fail("the call threw: " + out["error"])
    return out["result"]


def events(d):
    return run("return Tape.events(D);", d, needs=("Tape.events",))


def one(evs, **match):
    hits = [e for e in evs if all(e.get(k) == v for k, v in match.items())]
    assert len(hits) == 1, f"{len(hits)} events match {match}: {hits}"
    return hits[0]


def said(e):
    return f"{e.get('what') or ''} {e.get('detail') or ''}"


# ------------------------------------------------------------------ HTTP: the route and its files
@contextlib.contextmanager
def serving():
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def fetch(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=5) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


ASSET_TYPES = {"/tape_fmt.js": "text/javascript; charset=utf-8", "/tape_panels.js": "text/javascript; charset=utf-8",
               "/tape.js": "text/javascript; charset=utf-8", "/tape.css": "text/css; charset=utf-8",
               "/tape_panels.css": "text/css; charset=utf-8"}


def test_the_tape_page_is_served_uncached_at_tape():
    own("tape.html")
    with serving() as base:
        status, headers, body = fetch(base, "/tape")
    assert status == 200, "dashboard.py doesn't serve /tape yet"
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["Cache-Control"] == "no-store" and int(headers["Content-Length"]) == len(body)
    assert body == open(os.path.join(HERE, "tape.html"), "rb").read()


def test_the_tape_pages_five_files_are_served_as_themselves_with_their_types():
    for path, kind in ASSET_TYPES.items():
        assert path in dashboard.ASSETS, f"dashboard.ASSETS has no {path} yet"
        assert dashboard.ASSETS[path] == (path[1:], kind)
    for path in ASSET_TYPES:
        own(path[1:])
    with serving() as base:
        for path, kind in ASSET_TYPES.items():
            status, headers, body = fetch(base, path)
            assert (status, headers["Content-Type"], headers["Cache-Control"]) == (200, kind, "no-store"), path
            assert body == open(os.path.join(HERE, path[1:]), "rb").read(), path


def test_the_classic_page_is_still_served_at_the_root_unchanged():
    """The Tape page sits beside the classic one: / is dashboard.html byte for byte, and it loads none of Tape's files."""
    assert os.path.basename(dashboard.PAGE) == "dashboard.html"
    with serving() as base:
        status, headers, body = fetch(base, "/")
    assert status == 200 and headers["Content-Type"] == "text/html; charset=utf-8"
    assert body == open(dashboard.PAGE, "rb").read()
    page = body.decode("utf-8")
    loads = re.findall(r"<script\b[^>]*\bsrc=\"([^\"]+)\"", page) + re.findall(r"<link\b[^>]*\bhref=\"([^\"]+)\"", page)
    assert not [u for u in loads if "tape" in u], loads


# ------------------------------------------------------------------ tape.html: the shell and its look
def tags(page, name):
    """Each <name ...> tag's attributes as a dict."""
    return [dict((k.lower(), v) for k, _, v in re.findall(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", t))
            for t in re.findall(rf"<{name}\b([^>]*)>", page, re.I)]


def test_tape_html_loads_its_tokens_then_two_stylesheets_and_three_scripts_in_order():
    page = own("tape.html")
    assert [t["src"] for t in tags(page, "script") if "src" in t] == ["/tape_fmt.js", "/tape_panels.js", "/tape.js"]
    sheets = [t["href"] for t in tags(page, "link") if t.get("rel") == "stylesheet"]
    assert sheets == ["/tape.css", "/tape_panels.css"]
    first = re.search(r'<link\b[^>]*href="/tape\.css"', page)
    assert "</style>" in page and page.index("</style>") < first.start() < page.index("</head>")   # tokens first


LAYOUT = ("brand", "modes", "navBal", "status", "haltTop", "banners", "strip", "lp", "ltabs", "lpanel", "cp",
          "chartHead", "chart", "tp", "tapeHead", "openNow", "filters", "feed", "foot")


def test_tape_html_has_the_layout_in_the_spec():
    page = own("tape.html")
    body = page[page.index("<body"):]
    for i in LAYOUT:
        assert body.count(f'id="{i}"') == 1, f'tape.html needs one id="{i}"'
    at = [body.index(f'id="{i}"') for i in LAYOUT]
    assert at == sorted(at), "the ids aren't in the spec's order"
    assert re.search(r'<header\b[^>]*class="[^"]*\btop\b', body) and re.search(r'<main\b[^>]*class="[^"]*\bmain\b', body)
    main = body[body.index("<main"):]                                 # the header has a .right of its own
    left, right = re.search(r'class="[^"]*\bleft\b', main), re.search(r'class="[^"]*\bright\b', main)
    assert left and right, "main.main needs a .left and a .right"
    assert left.start() < main.index('id="lp"') < main.index('id="cp"') < right.start() < main.index('id="tp"')
    for p in ("lp", "cp", "tp"):                                     # the three panels
        assert re.search(rf'<section\b(?=[^>]*\bid="{p}")(?=[^>]*class="[^"]*\bpanel\b)[^>]*>', body), p


def test_tape_html_is_dark_fits_a_phone_shows_keyboard_focus_and_respects_reduced_motion():
    page = own("tape.html")
    assert any(t.get("name") == "viewport" and "width=device-width" in t.get("content", "") for t in tags(page, "meta"))
    style = "".join(re.findall(r"<style>(.*?)</style>", page, re.S))
    assert re.search(r"color-scheme\s*:\s*dark", style) or \
        any(t.get("name") == "color-scheme" and t.get("content") == "dark" for t in tags(page, "meta"))
    assert ":focus-visible" in style
    assert re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)", style)


TOKENS = {"--abyss": "#050506", "--panel": "#0e0e11", "--raised": "#17171b", "--slate": "112,113,135",
          "--ink": "#ffffff", "--ink-2": "#cbcbd3", "--muted": "#85869b", "--win": "#00da80", "--loss": "#ff3d5a",
          "--warn": "#f0a63a", "--violet": "#5741d8", "--violet-ink": "#9a8cff", "--r-panel": "2px", "--r-btn": "4px",
          "--seam": "4px", "--fs-10": "10px", "--fs-12": "12px", "--fs-14": "14px", "--fs-16": "16px",
          "--fs-20": "20px", "--fs-28": "28px"}
TOKENS_ANY = ("--line", "--line-soft", "--win-wash", "--loss-wash", "--warn-wash", "--sans", "--mono")


def test_tape_html_defines_the_terminal_look_tokens():
    page = own("tape.html")
    style = re.sub(r"/\*.*?\*/", "", "".join(re.findall(r"<style>(.*?)</style>", page, re.S)), flags=re.S)
    root = re.search(r":root\s*\{(.*?)\}", style, re.S)
    assert root, "tape.html has no :root block of tokens"
    have = {k: re.sub(r"\s+", "", v).lower() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root.group(1))}
    have = {k: re.sub(r"^#([0-9a-f])([0-9a-f])([0-9a-f])$", r"#\1\1\2\2\3\3", v) for k, v in have.items()}   # #fff
    assert {k: have.get(k) for k in TOKENS} == TOKENS
    assert [k for k in TOKENS_ANY if k not in have] == []


# ------------------------------------------------------------------ rules every page keeps, read as text
OUTSIDE = ("tape.html", "tape.css", "tape_panels.css", "tape.js", "tape_panels.js")
KALSHI = re.compile(r"^(?:https?:)?//(?:[\w-]+\.)*kalshi\.com(?:[/:?#]|$)", re.I)


def test_nothing_loads_from_outside():
    """No CDN, no web fonts, no remote images: the page has to work on a home network with no internet. Links out to
    a market on kalshi.com are fine (and the SVG namespace, which is a name, not a load)."""
    missing, bad = [], {}
    for name in OUTSIDE:
        if not os.path.exists(os.path.join(HERE, name)):
            missing.append(name)
            continue
        s = code(re.sub(r"<!--.*?-->", "", own(name), flags=re.S))
        loads = re.findall(r"""\b(?:src|href)\s*=\s*\\?["'`]?\s*((?:https?:|wss?:)?//[^"'`\s>)]*)""", s, re.I)
        loads += re.findall(r"""@import\s+(?:url\()?\s*["']?\s*((?:https?:)?//[^"');\s]*)""", s, re.I)
        loads += re.findall(r"""url\(\s*["']?\s*((?:https?:)?//[^"')\s]*)""", s, re.I)
        loads += re.findall(r"""\b(?:fetch|import|WebSocket|EventSource)\s*\(\s*["'`]\s*((?:https?:|wss?:)?//[^"'`\s]*)""", s)
        urls = re.findall(r"(?:https?|wss?)://[^\s\"'`)<>]+", s)
        wrong = [u for u in loads if not KALSHI.match(u)] + \
                [u for u in urls if not KALSHI.match(u) and not re.match(r"https?://(?:www\.)?w3\.org/", u)]
        if wrong:
            bad[name] = sorted(set(wrong))
    assert bad == {}, f"loads from outside: {bad}"
    assert missing == [], f"{', '.join(missing)} doesn't exist yet"


def test_words_stay_in_sentence_case():
    missing, caps = [], []
    for name in ("tape.html", "tape.css", "tape_panels.css"):
        if not os.path.exists(os.path.join(HERE, name)):
            missing.append(name)
        elif re.search(r"text-transform\s*:\s*uppercase", code(own(name)), re.I):
            caps.append(name)
    assert caps == [], f"text-transform: uppercase in {caps}"
    assert missing == [], f"{', '.join(missing)} doesn't exist yet"


def test_the_page_can_halt_in_two_taps():
    """One halt button, always in reach: a POST to /api/halt, and only on a second tap, so a stray touch can't."""
    js = code(own("tape.js"))
    assert "/api/halt" in js and re.search(r"""method\s*:\s*["']POST["']""", js)
    assert re.search(r"\barm(ed)?\b", js), "no armed state: one stray tap would halt the bot"


def test_nothing_on_the_page_can_resume_the_bot():
    """There is no resume from the page, ever: it tells you the command (python bot.py --resume) instead."""
    for name in ("tape.html", "tape.js", "tape_panels.js"):
        s = code(own(name))
        assert not re.search(r"/api/[\w/-]*resume", s, re.I), name
        assert not re.search(r"\bresume\s*\(", s), name


def test_the_three_scripts_parse():
    if not NODE:
        pytest.skip("node isn't installed")
    missing, broken = [], {}
    for name in SCRIPTS:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        r = subprocess.run([NODE, "--check", path], capture_output=True, text=True)
        if r.returncode:
            broken[name] = r.stderr
    assert broken == {}
    assert missing == [], f"{', '.join(missing)} doesn't exist yet"


# ------------------------------------------------------------------ the scripts load in node
@needs_node
def test_the_shared_formats_load_in_node_the_way_the_tests_load_every_script():
    """tape_fmt.js is written already: this proves the runner itself works, so a failure elsewhere is the page's."""
    r = run("return [TapeFmt.cents(0.94), TapeFmt.cents(0.999), TapeFmt.money(1000, 0), "
            "TapeFmt.symOf('KXBTC15M-26NOV061745-45'), TapeFmt.groupOf('GOLD'), D.x];", {"x": 1}, needs=("TapeFmt.cents",))
    assert r == ["94¢", "99.9¢", "$1,000", "BTC", "metals", 1]


@needs_node
@pytest.mark.parametrize("obj, names", [("Tape", TAPE_FUNCTIONS), ("TapePanels", PANEL_FUNCTIONS)], ids=["tape", "panels"])
def test_each_script_loads_with_only_window_defined_and_puts_its_functions_on_it(obj, names):
    """No document, no fetch, no timers in node: anything that touches the page waits for a document."""
    assert run("return 1;", needs=tuple(f"{obj}.{n}" for n in names)) == 1


# ------------------------------------------------------------------ Tape.events: the tape itself
@needs_node
def test_the_tape_is_every_decision_settled_bet_and_error_newest_first():
    d = paper_state()
    ev = events(d)
    assert len(ev) == len(d["decisions"]) + len(d["recentBets"]) + len(d["errors"])
    ts = [e["ts"] for e in ev]
    assert ts == sorted(ts, reverse=True)


@needs_node
def test_a_settled_bet_is_won_or_lost_at_its_settle_time_with_its_profit():
    d = paper_state()
    ev = events(d)
    for b in d["recentBets"]:
        e = one(ev, ticker=b["ticker"], kind=b["status"])
        assert e["ts"] == pytest.approx(b["settled_ts"]) and e["pnl"] == pytest.approx(b["pnl"])
        assert (e["mkt"], e["side"]) == (sym_of(b["ticker"]), b["side"])
    assert [e["mkt"] for e in ev if e["kind"] == "lost"] == ["GOLD"]


@needs_node
def test_a_skip_reads_without_the_favorite_at_prefix():
    ev = events(paper_state())
    sol = one(ev, kind="skip", mkt="SOL")
    assert "outside 92-99.9c" in said(sol) and "favorite at" not in said(sol)
    doge = one(ev, kind="skip", mkt="DOGE")                       # any other reason is kept whole
    assert "warning sign: its ask is 3.0c over its bid" in said(doge)


@needs_node
def test_a_bet_picks_up_its_own_orders_fill():
    ev = events(paper_state())
    btc = one(ev, kind="bet", ticker=tk("BTC", W0))
    assert "filled 17 of 17" in btc["detail"]
    assert (btc["mkt"], btc["side"], btc["price"]) == ("BTC", "yes", 0.96)
    eth = one(ev, kind="bet", ticker=tk("ETH", W0))               # Kalshi refused it
    assert "got none" in eth["detail"] and "market closed" in eth["detail"]
    old = one(ev, kind="bet", ticker=tk("ETH", W0 - 2700))         # the same market an hour before: its own order
    assert "filled 18 of 18" in old["detail"]


@needs_node
def test_errors_and_any_other_action_keep_a_kind_of_their_own():
    ev = events(paper_state())
    err = one(ev, kind="error")
    assert err["ts"] == pytest.approx(W0 + 480.41) and err["mkt"] == "ETH"
    assert one(ev, kind="halted")["mkt"] == "HYPE"                # a word the bot logged, shown as is
    assert {e["kind"] for e in ev} == {"skip", "bet", "halted", "won", "lost", "error"}


@needs_node
def test_every_event_has_a_key_of_its_own_that_holds_across_refreshes():
    """The fresh-row highlight leans on it: the same event keeps its key on every read, and a new one doesn't move
    anyone else's (even with every decision of a window logged at the same moment)."""
    now = paper_state()
    later = json.loads(json.dumps(now))                            # the next read: the same ledger rows, plus ...
    settled = bet("BTC", W0, "won", price=0.96, contracts=17)       # ... this window's bet settled (the same row) ...
    settled["id"] = now["openBets"][0]["id"]
    later["openBets"], later["recentBets"] = [], [settled] + later["recentBets"]
    later["decisions"].insert(0, dec("BTC", W0 + 900, "skip", "yes", 0.55,   # ... and the next window's first decision
                                     "favorite at 55.0c is outside 92-99.9c"))
    body = ("const a = Tape.events(D.now).map((e) => e.key), b = Tape.events(JSON.parse(JSON.stringify(D.now)))"
            ".map((e) => e.key), c = Tape.events(D.later).map((e) => e.key); return [a, b, c];")
    a, b, c = run(body, {"now": now, "later": later}, needs=("Tape.events",))
    assert all(k not in (None, "") for k in a) and len({str(k) for k in a}) == len(a)
    assert a == b
    assert len({str(k) for k in c}) == len(c) and set(map(str, a)) <= set(map(str, c))


# ------------------------------------------------------------------ Tape.filter
FILTERS = """const ev = Tape.events(D);
const pick = (f, m) => Tape.filter(ev, f, m).map((e) => e.key);
return {ev: ev.map((e) => [e.key, e.kind, e.mkt]), all: pick("all"), bets: pick("bets"), losses: pick("losses"),
        btc: pick("all", "BTC"), btcLosses: pick("losses", "BTC"), goldLosses: pick("losses", "GOLD"),
        ethBets: pick("bets", "ETH")};"""


@needs_node
def test_the_filters_show_everything_everything_but_skips_or_only_losses():
    r = run(FILTERS, paper_state(), needs=("Tape.events", "Tape.filter"))
    assert r["all"] == [k for k, _, _ in r["ev"]]
    assert r["bets"] == [k for k, kind, _ in r["ev"] if kind != "skip"]    # halts and errors stay in
    assert r["losses"] == [k for k, kind, _ in r["ev"] if kind == "lost"] and len(r["losses"]) == 1


@needs_node
def test_a_market_filter_keeps_only_that_market():
    r = run(FILTERS, paper_state(), needs=("Tape.events", "Tape.filter"))
    assert r["btc"] == [k for k, _, m in r["ev"] if m == "BTC"] and len(r["btc"]) == 3
    assert r["btcLosses"] == []
    assert r["goldLosses"] == [k for k, kind, m in r["ev"] if m == "GOLD" and kind == "lost"] and r["goldLosses"]
    assert r["ethBets"] == [k for k, kind, m in r["ev"] if m == "ETH" and kind != "skip"]


# ------------------------------------------------------------------ Tape.feedHtml
XSS = "<img src=x onerror=alert(1)>"


@needs_node
def test_the_feed_escapes_every_string_from_the_server():
    d = paper_state()
    d["decisions"][0]["reason"] = XSS                                          # the SOL skip
    d["decisions"][-1]["reason"] = "halted: <script>alert(2)</script>"
    d["errors"][0]["response"] = "<img src=y onerror=alert(3)>"
    d["orders"][0]["error"] = "<svg onload=alert(4)>"                           # the ETH order that got none
    markup = run("return Tape.feedHtml(Tape.events(D), new Set());", d, needs=("Tape.events", "Tape.feedHtml"))
    low = markup.lower()
    assert "<img" not in low and "<script" not in low and "<svg onload" not in low
    assert esc(XSS) in markup                                                   # shown, as text


@needs_node
def test_the_feed_reads_as_the_tape_with_skips_shortened():
    t = text(run("return Tape.feedHtml(Tape.events(D), new Set());", paper_state(),
                 needs=("Tape.events", "Tape.feedHtml")))
    assert "outside 92-99.9c" in t and "favorite at 61.0c is" not in t
    assert "filled 17 of 17" in t and "BTC" in t and "GOLD" in t


@needs_node
def test_only_the_fresh_rows_are_marked_fresh():
    body = """const ev = Tape.events(D);
return [0, 1, 2].map((n) => Tape.feedHtml(ev, new Set(ev.slice(0, n).map((e) => e.key))));"""
    out = run(body, paper_state(), needs=("Tape.events", "Tape.feedHtml"))
    fresh = [sum("fresh" in c.split() for _, c in re.findall(r"""class\s*=\s*(["'])(.*?)\1""", m)) for m in out]
    assert fresh == [0, 1, 2]


# ------------------------------------------------------------------ Tape.openHtml: the open bets above the feed
@needs_node
def test_with_no_open_bets_one_quiet_line_says_so():
    markup = run(f"return Tape.openHtml(D, {NOW});", paper_state(openBets=[], unrealized=0.0), needs=("Tape.openHtml",))
    assert "No open bets" in text(markup)


@needs_node
def test_an_open_bet_shows_its_market_price_and_settle_time():
    d = paper_state()
    markup, settles = run(f"return [Tape.openHtml(D, {NOW}), TapeFmt.hhmm(D.openBets[0].close_ts)];", d,
                          needs=("Tape.openHtml",))
    t = text(markup)
    assert "BTC" in t and "96¢" in t and norm(settles) in t
    assert "No open bets" not in t


# ------------------------------------------------------------------ Tape.grid: every bet, a column per window
def grid_rows(g):
    return {x["group"]: [r["mkt"] for r in x["rows"]] for x in g["groups"]}


def grid_cells(g):
    return {r["mkt"]: dict(zip(g["cols"], r["cells"])) for x in g["groups"] for r in x["rows"]}


@needs_node
def test_the_grid_groups_crypto_metals_energy_then_other_each_a_to_z():
    """A market the shared list doesn't know goes under other, unless the live board says which class it is in."""
    d = paper_state()
    d["bySeries"] += [series_row("EURUSD", 3, 3, 0.4, 50.0), series_row("ALUM", 2, 2, 0.2, 30.0)]
    d["openBets"].append(bet("XRP", W0, "open"))                     # only an open bet: it still gets a row
    plain, boarded = run(f"return [Tape.grid(D.d, {NOW}, null), Tape.grid(D.d, {NOW}, D.board)];",
                         {"d": d, "board": board_reply(markets=[bm("ALUM", "metals", "yes", 0.95)])},
                         needs=("Tape.grid",))
    assert [x["group"] for x in plain["groups"]] == ["crypto", "metals", "energy", "other"]
    assert grid_rows(plain) == {"crypto": ["BTC", "ETH", "SOL", "XRP"], "metals": ["GOLD"], "energy": ["NATGAS"],
                                "other": ["ALUM", "EURUSD"]}
    assert grid_rows(boarded) == {"crypto": ["BTC", "ETH", "SOL", "XRP"], "metals": ["ALUM", "GOLD"],
                                  "energy": ["NATGAS"], "other": ["EURUSD"]}


@needs_node
def test_each_cell_says_how_that_markets_bet_in_that_window_did_up_to_the_current_window():
    g = run(f"return Tape.grid(D, {NOW}, null);", paper_state(), needs=("Tape.grid",))
    assert g["cols"] == [W0 - 2700, W0 - 1800, W0 - 900, W0]           # the oldest bet's window to this one
    cells = grid_cells(g)
    assert all(len(r["cells"]) == len(g["cols"]) for x in g["groups"] for r in x["rows"])
    assert cells["BTC"] == {W0 - 2700: "", W0 - 1800: "", W0 - 900: "won", W0: "open"}
    assert cells["GOLD"][W0 - 900] == "lost" and cells["NATGAS"][W0 - 1800] == "won" and cells["ETH"][W0 - 2700] == "won"
    assert set(cells["SOL"].values()) == {""}                          # in bySeries, with no recent bet


@needs_node
def test_the_grid_keeps_only_the_last_96_windows():
    d = paper_state()
    d["recentBets"].append(bet("ETH", W0 - 200 * 900, "won"))          # a bet two days back
    g = run(f"return Tape.grid(D, {NOW}, null);", d, needs=("Tape.grid",))
    assert len(g["cols"]) == 96 and g["cols"][-1] == W0 and g["cols"][0] == W0 - 95 * 900
    assert all(len(r["cells"]) == 96 for x in g["groups"] for r in x["rows"])


@needs_node
def test_in_one_cell_a_loss_beats_an_open_bet_which_beats_a_win():
    w = W0 - 900
    d = paper_state(recentBets=[bet("BTC", w, "won"), bet("BTC", w, "lost"), bet("DOGE", w, "lost"),
                                bet("DOGE", w, "won"), bet("ETH", w, "won"), bet("SOL", w, "lost")],
                    openBets=[bet("ETH", w, "open"), bet("SOL", w, "open")])
    cells = grid_cells(run(f"return Tape.grid(D, {NOW}, null);", d, needs=("Tape.grid",)))
    assert {m: cells[m][w] for m in ("BTC", "DOGE", "ETH", "SOL")} == {"BTC": "lost", "DOGE": "lost", "ETH": "open",
                                                                       "SOL": "lost"}


@needs_node
def test_each_market_in_the_grid_is_a_button_that_filters_the_tape():
    body = f"const g = Tape.grid(D, {NOW}, null); return [Tape.gridHtml(g), g.groups.flatMap((x) => x.rows.map((r) => r.mkt))];"
    markup, mkts = run(body, paper_state(), needs=("Tape.grid", "Tape.gridHtml"))
    assert mkts
    for m in mkts:
        assert re.search(rf"""<button\b[^>]*\bdata-mkt=(["']){m}\1""", markup), m


# ------------------------------------------------------------------ Tape.countdown
@needs_node
def test_the_countdown_says_halted_not_running_blackout_entering_or_the_time_left():
    halted = paper_state(halt={"ts": iso(NOW - 300), "reason": "halted from the dashboard", "by": "you"})
    paused = paper_state(blackout={"what": "Fed decision", "from": W0 + 300.0, "to": W0 + 5700.0, "active": True})
    cases = {   # name: (state, now, running) -> (text, class or None for any)
        "halted": (("halted", W0 + 200, True), ("Halted", "down")),
        "halted beats not running": (("halted", W0 + 200, False), ("Halted", "down")),
        "not running": (("plain", W0 + 200, False), ("Not running", "down")),
        "blackout, even at minute 8": (("paused", W0 + 480, True), ("Blackout", None)),
        "entering at 480 s": (("plain", W0 + 480, True), ("Entering now", None)),
        "entering at 525 s": (("plain", W0 + 525, True), ("Entering now", None)),
        "280 s to this window's entry": (("plain", W0 + 200, True), ("4:40", None)),
        "854 s to the next window's": (("plain", W0 + 526, True), ("14:14", None)),
    }
    out = run("return D.cases.map(([s, now, running]) => Tape.countdown(D.states[s], now, running));",
              {"states": {"plain": paper_state(), "halted": halted, "paused": paused},
               "cases": [c for c, _ in cases.values()]}, needs=("Tape.countdown",))
    got = {name: (re.sub(r"^0(\d:\d\d)$", r"\1", r["text"]), r.get("cls") if want[1] else None)
           for (name, (_, want)), r in zip(cases.items(), out)}                 # "04:40" reads as "4:40"
    assert got == {name: want for name, (_, want) in cases.items()}


# ------------------------------------------------------------------ Tape.strip: one row of figures
def strip_says(items):
    return " | ".join(" ".join(i.get(k) or "" for k in ("label", "value", "sub")) for i in items)


@needs_node
def test_the_strip_shows_the_account_value_and_the_next_entry():
    """The bot's books (what it started with, what settled, and the open bets at their price now); on a live account
    Kalshi's own reading of it."""
    body = f"""const o = {{hideBal: false, now: {NOW}, running: true}};
return [Tape.strip(D.paper, o), Tape.strip(D.live, o), Tape.countdown(D.paper, {NOW}, true).text];"""
    paper, live, next_entry = run(body, {"paper": paper_state(), "live": live_state()},
                                  needs=("Tape.strip", "Tape.countdown"))
    assert paper and all("label" in i and "value" in i for i in paper)
    d = paper_state()
    assert shows(strip_says(paper), money(d["bankroll"] + d["unrealized"]))        # $1,205.23
    assert shows(strip_says(paper), next_entry)
    assert shows(strip_says(live), "$1,317.50")


@needs_node
def test_with_the_balance_hidden_the_account_shows_its_change_not_its_dollars():
    items = run(f"return Tape.strip(D, {{hideBal: true, now: {NOW}, running: true}});", paper_state(),
                needs=("Tape.strip",))
    says = strip_says(items)
    assert "1,205.23" not in text(says) and "1,205.23" not in joined(says)
    assert shows(says, "+20.5%")                                       # $1,205.23 against the $1,000.00 it started with


@needs_node
def test_a_paper_account_also_shows_its_simulation():
    body = f"""const o = {{hideBal: false, now: {NOW}, running: true}};
return [Tape.strip(D.paper, o), Tape.strip(D.bare, o), TapeFmt.money(D.paper.sim.start, 0) + " simulation"];"""
    bare = paper_state()
    del bare["sim"]
    paper, without, label = run(body, {"paper": paper_state(), "bare": bare}, needs=("Tape.strip",))
    assert label == "$1,000 simulation"
    sims = [i for i in paper if label in text(i["label"])]
    assert len(sims) == 1, [text(i["label"]) for i in paper]
    says = strip_says(sims)
    assert shows(says, "$2,505.13") and shows(says, "+150.5%")
    assert not [i for i in without if "simulation" in text(i["label"]).lower()]


# ------------------------------------------------------------------ Tape.banners
@needs_node
def test_a_halt_says_how_to_resume_and_shows_the_reason_escaped():
    d = paper_state(halt={"ts": iso(NOW - 300), "reason": XSS, "by": "you"})
    markup = run(f"return Tape.banners(D, {NOW}, true);", d, needs=("Tape.banners",))
    assert "python bot.py --resume" in text(markup)
    assert "<img" not in markup and esc(XSS) in markup


@needs_node
def test_a_bot_that_isnt_running_says_so_and_with_nothing_wrong_there_is_no_banner():
    stopped, quiet = run(f"return [Tape.banners(D, {NOW}, false), Tape.banners(D, {NOW}, true)];", paper_state(),
                         needs=("Tape.banners",))
    assert re.search(r"not running", text(stopped), re.I)
    assert text(quiet) == ""


# ------------------------------------------------------------------ TapePanels: the left-hand tabs
@needs_node
def test_the_live_board_lists_only_the_groups_the_bot_trades_and_links_each_market_to_kalshi():
    body = f"""return [TapePanels.board(D.board, D.data, {NOW}, new Map()),
  D.board.live.markets.map((m) => [m.label, m.group, TapeFmt.kalshiUrl(m.ticker)])];"""
    markup, ms = run(body, {"board": board_reply(), "data": paper_state(groups=["crypto", "energy"])},
                     needs=("TapePanels.board",))
    t = text(markup)
    for label, group, url in ms:
        if group in ("crypto", "energy"):
            assert label in t and f'href="{esc(url)}"' in markup, label
        else:
            assert label not in t and url not in markup, label        # metals and the coin race: not traded


@needs_node
def test_the_board_status_says_streaming_polling_stale_or_offline():
    body = f"""return [TapePanels.boardStatus(D.stream, false, {NOW}), TapePanels.boardStatus(D.stream, true, {NOW}),
  TapePanels.boardStatus(D.poll, false, {NOW}), TapePanels.boardStatus(D.stale, false, {NOW})];"""
    on, off, poll, stale = run(body, {"stream": board_reply(), "poll": board_reply(source="poll"),
                                      "stale": board_reply(age=120)}, needs=("TapePanels.boardStatus",))
    assert on["kind"] == "on" and "Streaming" in text(on["text"]) and "minute 11 of 15" in text(on["text"])
    assert off["kind"] == "off" and "Offline" in text(off["text"])
    assert poll["kind"] == "warn" and "Polling" in text(poll["text"])
    assert stale["kind"] == "warn" and "Stale" in text(stale["text"])


@needs_node
def test_with_no_orders_yet_the_orders_tab_says_how_orders_work():
    d = paper_state(orders=[], fills=dict(ZERO), fillsAll={**ZERO, "since": None}, fillsHour=dict(ZERO),
                    fillsBySize=[], fillWindows=[])
    t = text(run("return TapePanels.orders(D);", d, needs=("TapePanels.orders",)))
    assert "minute 8" in t and re.search(r"immediate.or.cancel", t, re.I), t


@needs_node
def test_by_market_lists_every_market_the_bot_has_bet():
    d = paper_state()
    t = text(run("return TapePanels.markets(D);", d, needs=("TapePanels.markets",)))
    assert [sym_of(s["series"]) for s in d["bySeries"] if sym_of(s["series"]) not in t] == []


@needs_node
def test_the_rules_give_the_92_to_99_9_band_and_the_resume_command():
    t = text(run("return TapePanels.rules(D);", paper_state(), needs=("TapePanels.rules",)))
    assert "92¢" in t and "99.9¢" in t and "python bot.py --resume" in t


@needs_node
def test_with_no_buy_orders_in_7_days_the_fill_rate_tab_says_so_and_with_some_it_draws_the_chart():
    none, some = run("return [TapePanels.fills(D.none, 600), TapePanels.fills(D.some, 600)];",
                     {"none": paper_state(fillWindows=[], fillOff=[]), "some": paper_state()},
                     needs=("TapePanels.fills",))
    assert re.search(r"no buy orders in the (last|past) (7|seven) days", text(none), re.I), text(none)
    assert "<svg" in some


# ------------------------------------------------------------------ the long view: the simulation since markets opened
# Added Nov 8, 2026: an option to see the paper account's chart from the first days the markets opened, with a mark
# where metals and the other asset classes came in. The option is the $1,000
# simulation, the bot's rules replayed since Kalshi's first 15-minute market (Dec 10, 2025). On it, each asset class
# gets a rule down the plot where its first bet fell and a shaded band under the plot from there to the end; each
# market's own first bet is a notch on its class's band, named on hover. Classes whose first bets fall within two days
# of each other share one rule and one label ("Metals and energy" came in on the same day, Aug 3, 2026).
SIM_T0 = 1765324800                                   # 2025-12-10T00:00:00Z
STEP = 6 * 3600


def sim_pts(days=330):
    return [[SIM_T0 + i * STEP, 1000 + i * 0.4] for i in range(days * 4)]


LONG = {"pts": sim_pts(),
        "classes": [{"key": "crypto", "first": "2025-12-20T00:00:00+00:00"},
                    {"key": "energy", "first": "2026-08-03T17:00:00+00:00"},
                    {"key": "metals", "first": "2026-08-03T17:30:00+00:00"}],
        "markets": [{"key": "BTC", "first": "2025-12-20T00:00:00+00:00"},
                    {"key": "BNB", "first": "2026-03-19T04:00:00+00:00"},
                    {"key": "DOGE", "first": "2026-03-19T02:45:00+00:00"},
                    {"key": "GOLD", "first": "2026-08-03T20:30:00+00:00"},
                    {"key": "COPPER", "first": "2026-08-28T14:00:00+00:00"},
                    {"key": "WTI", "first": "2026-08-03T17:00:00+00:00"}]}


def long_chart(data=None, extra="{}"):
    return run("return Tape.chartHtml(D.pts, Object.assign({w: 900, h: 300, base: 1000, losses: false, "
               "classes: D.classes, markets: D.markets}, " + extra + "));", data or LONG, needs=("Tape.chartHtml",))


@needs_node
def test_the_long_view_marks_each_asset_class_with_a_rule_and_a_band():
    svg = long_chart()
    t = text(svg)
    assert len(re.findall(r'class="ch-cls"', svg)) == 2, svg          # crypto, then metals and energy together
    assert len(re.findall(r'class="ch-band ', svg)) == 3                # a band each: crypto, energy, metals
    assert "Crypto" in t and re.search(r"Metals and energy|Energy and metals", t), t


@needs_node
def test_each_class_is_named_with_the_day_of_its_first_bet_read_off_the_date_itself():
    """The day comes off the ISO string, as backtest.js reads it: midnight UTC on Dec 20 is still Dec 19 in the
    tests' Los Angeles time, and a label must not move a class's first bet to the day before."""
    t = text(long_chart())
    assert "Dec 20" in t and "Dec 19" not in t, t
    assert "Aug 3" in t, t


@needs_node
def test_a_markets_first_bet_is_a_notch_on_its_class_band_named_on_hover():
    svg = long_chart()
    notches = re.findall(r'<g class="ch-mk">.*?</g>', svg, re.S)
    assert notches, svg
    titles = " ".join(re.findall(r"<title>(.*?)</title>", " ".join(notches), re.S))
    assert re.search(r"BNB, DOGE|DOGE, BNB", titles), titles             # same day: one notch naming both
    assert "COPPER" in titles and "GOLD" in titles, titles


@needs_node
def test_a_class_outside_the_range_gets_no_rule_and_one_from_before_it_starts_its_band_at_the_left_edge():
    d = {**LONG, "pts": [p for p in LONG["pts"] if p[0] >= SIM_T0 + 120 * 86400]}   # from mid-April: crypto came first
    svg = long_chart(d)
    assert len(re.findall(r'class="ch-cls"', svg)) == 1                 # metals and energy only
    assert len(re.findall(r'class="ch-band ', svg)) == 3                # crypto's band still runs the whole width
    early = {**LONG, "pts": [p for p in LONG["pts"] if p[0] < SIM_T0 + 200 * 86400]}   # ends before August
    svg = long_chart(early)
    assert "Metals" not in text(svg) and len(re.findall(r'class="ch-band ', svg)) == 1


@needs_node
def test_class_and_market_names_from_the_server_are_escaped():
    d = {**LONG, "classes": [{"key": "<b>x</b>", "first": "2026-02-01T00:00:00+00:00"}],
         "markets": [{"key": "<i>y</i>", "first": "2026-02-01T00:00:00+00:00"}]}
    svg = long_chart(d)
    assert "<b>x</b>" not in svg and "<i>y</i>" not in svg and "&lt;b&gt;" in svg


@needs_node
def test_without_classes_the_chart_has_no_marks():
    svg = run("return Tape.chartHtml(D.pts, {w: 900, h: 300, base: 1000});", LONG, needs=("Tape.chartHtml",))
    assert "ch-cls" not in svg and "ch-band" not in svg


def test_the_chart_offers_the_view_since_markets_opened_with_month_ranges():
    js = code(own("tape.js"))
    assert "Since markets opened" in js
    assert '"1M"' in js and '"3M"' in js                                 # the long view's ranges; a day is noise there
    assert re.search(r"classes:\s*[^,}]*groups", js) and re.search(r"markets:\s*[^,}]*markets", js)
