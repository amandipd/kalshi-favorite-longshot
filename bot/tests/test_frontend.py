"""dashboard.html against the server that feeds it: it may only read fields the API really sends, it must
load nothing from outside (it may run on a machine that is offline), it can halt but not resume, and server text
can't inject markup. The script's syntax is checked with Node when it's installed.

    python -m pytest tests/test_frontend.py -q
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from test_bot import W
from test_dashboard_more import NOW, Exchange, add_bet, home, mode_db, quiet  # noqa: F401 (home is a fixture)

HTML = open(dashboard.PAGE, encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)


def full_state(home):
    """A live account with a bit of everything, so every field the API can send is present."""
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", status="won")
    add_bet(db, "KXBTC15M-OPEN", status="open")
    db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
               (NOW, "KXBTC15M-1", "KXBTC15M", "yes", 0.96, "bet", "bought"))
    db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
               (NOW, "KXBTC15M-1", "c", "{}", 400, '"no"'))
    bot.set_meta(db, "heartbeat", NOW)
    db.commit()
    bot.set_halt(NOW, "testing", "you")
    return dashboard.state("live-prod")


def test_the_page_only_reads_fields_the_api_sends(home):
    s = full_state(home)
    mode_db(home, "dry-prod")
    dry = dashboard.state("dry-prod")     # a paper mode's state: no kalshi, a "sim" in its place
    reads = r"\.([A-Za-z_]\w*)\b(?!\()"   # a field, not a method call (the helpers use a local `d` for a Date)
    used = set(re.findall(r"\bd" + reads, SCRIPT)) | set(re.findall(r"\bdata" + reads, SCRIPT))
    assert used, "found no field reads: the pattern needs updating"
    assert used <= set(s) | set(dry), f"the page reads {sorted(used - set(s) - set(dry))}, which the server doesn't send"


def test_the_pages_limits_are_ones_the_server_sends_and_its_defaults_match(home):
    s = full_state(home)
    read = set(re.findall(r"\bL\.([A-Za-z_]\w*)", SCRIPT))
    defaults = dict(re.findall(r"(\w+): ([\d.]+)", re.search(r"const LIMITS = \{(.*?)\};", SCRIPT, re.S).group(1)))
    assert read and read <= set(s["limits"]), sorted(read - set(s["limits"]))
    assert set(defaults) == set(s["limits"])                                  # the fallback names every limit ...
    for k, v in defaults.items():
        assert float(v) == pytest.approx(s["limits"][k], abs=1), k           # ... and starts near the real value


def test_the_page_loads_nothing_from_outside():
    """No fonts, scripts or styles from a CDN: it has to work on a home network with no internet."""
    # only the Live Research, Latency and Backtest tabs' own scripts and styles, from this server
    assert re.findall(r"<script[^>]+src=\"([^\"]+)\"", HTML) == ["/live_research.js", "/latency.js",
                                                                  "/backtest.js"]
    assert re.findall(r"<link[^>]+rel=\"stylesheet\"[^>]+href=\"([^\"]+)\"", HTML) == ["/live_research.css", "/latency.css",
                                                                                        "/backtest.css", "/exchange.css"]
    own = [open(os.path.join(os.path.dirname(dashboard.PAGE), f), encoding="utf-8").read()
           for f in ("live_research.js", "live_research.css", "latency.js", "latency.css",
                     "backtest.js", "backtest.css", "exchange.css")]
    for text in (HTML, *own):
        assert "@import" not in text and "googleapis" not in text
        urls = set(re.findall(r"https?://[^\s\"'`)]+", text))
        assert {u for u in urls if "kalshi.com" not in u and "w3.org" not in u} == set(), urls   # only links out to Kalshi


def test_the_page_can_halt_but_never_resume():
    assert "/api/halt" in SCRIPT and 'method: "POST"' in SCRIPT
    assert "/api/resume" not in HTML and not re.search(r"resume\s*\(", SCRIPT)
    assert "python bot.py --resume" in HTML          # it tells you the command instead
    assert "data-halt" in SCRIPT and 'id="haltTop"' in HTML   # one button, in the header, so it's always in reach


def test_halting_takes_two_taps():
    assert "armed" in SCRIPT and "Tap again to halt" in SCRIPT


def test_the_page_is_dark_only_and_built_for_small_screens():
    assert 'name="viewport"' in HTML and 'name="color-scheme" content="dark"' in HTML
    assert "color-scheme: dark" in HTML and "prefers-color-scheme" not in HTML
    assert "data-theme" not in HTML and 'id="theme"' not in HTML and 'dataset.theme' not in HTML
    assert "prefers-reduced-motion" in HTML and "@media (max-width: 560px)" in HTML and "@media (max-width: 400px)" in HTML


def test_server_text_is_escaped_before_it_becomes_markup():
    """Reasons, Kalshi's responses, errors and market names come from outside: none may reach a template raw."""
    raw = [t for t in re.findall(r"\$\{([^{}]*)\}", SCRIPT) if re.search(r"\.(reason|response|error|what|ticker)\b", t) and "esc(" not in t]
    allowed = {"kalshiUrl(b.ticker)"}   # wrapped in esc(...) by its caller
    assert [t for t in raw if t not in allowed and not t.startswith("market(")] == [], raw


def test_the_scripts_parse(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("node isn't installed")
    f = tmp_path / "dash.js"
    f.write_text('"use strict";' + SCRIPT, encoding="utf-8")
    r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------------------ the quiet default
def test_it_leads_with_the_account_the_chart_and_the_open_positions():
    body = HTML.split("<main")[1].split("</main>")[0]
    order = [body.index(f'id="{i}"') for i in ("banners", "hero", "chartPanel", "positions", "method", "more")]
    assert order == sorted(order)                                   # in that order, and nothing else in between


def test_everything_else_is_in_rows_that_start_closed():
    sections = re.findall(r'\["(\w+)", "([^"]+)", ', SCRIPT.split("function more(")[1])
    assert [s for s, _ in sections][:4] == ["numbers", "history", "stops", "settings"]   # the ones people read first
    ids = {s for s, _ in sections}
    assert {"numbers", "history", "stops", "settings", "decisions", "markets", "errors"} <= ids
    assert 'openSecs = new Set(parse("open", []))' in SCRIPT      # nothing is open until you open it
    # native rows; their separate "Expand all" button is gone: the Live tab's one Open all / Close all (data-folds,
    # the folds) opens and closes them along with the folds (test_folds_live.py)
    assert "<details" in SCRIPT and "data-folds" in SCRIPT
    assert "data-expand" not in SCRIPT and '"Expand all"' not in SCRIPT and ">Expand all<" not in SCRIPT


def test_the_optional_controls_start_hidden_and_remember_their_state():
    assert '<div id="chartCtl" class="chips" hidden>' in HTML     # the chart's $/%, range and table controls
    assert 'chartOpts = store.get("chartOpts") === "1"' in SCRIPT
    assert 'showSkips = store.get("skips") === "1"' in SCRIPT     # skipped markets are off the decisions log by default
    assert 'role="switch"' in SCRIPT


def test_the_balance_can_be_hidden_leaving_the_change_in_percent():
    assert 'hideBal = store.get("hideBal") === "1"' in SCRIPT      # shown until you hide it, then remembered
    assert "data-bal" in SCRIPT and 'aria-pressed="${hideBal}"' in SCRIPT
    hidden = SCRIPT.split("${hideBal ? `")[1].split("` : `")[0]   # the hero while hidden
    assert "spct(r)" in hidden                                      # the % since the start stays ...
    assert "money(" not in hidden and "signed(" not in hidden       # ... and no dollar figure is left to work it back from


def test_the_page_is_one_narrow_column():
    # (its "max-width: 760px" check went with the live-bot sidebar, whose .ls-body rule was the last one to have it)
    assert "grid-template-columns: 300px" not in HTML
    for gone in ('id="rail"', 'id="side"', 'class="stats"', 'id="tabsBox"'):
        assert gone not in HTML, gone


# ------------------------------------------------------------------ the tabs (the Historical Research tab went on Oct 15)
def test_a_mode_tab_comes_back_to_the_account():
    assert 'page = "account"; store.set("mode", mode)' in SCRIPT     # (Live Research's button: test_no_historical_research.py)


def test_the_live_tab_shows_each_orders_asked_and_filled_under_the_positions():
    assert HTML.index('<section id="positions"') < HTML.index('<section id="orders" aria-label="Orders: asked for, filled, won or lost">') < HTML.index('<section id="method"')
    assert 'for (const id of ["hero", "chartPanel", "board", "fills", "positions", "orders", "method", "more"]) $(id).hidden = other;' in SCRIPT
    assert "positions(); fillsBlock(); ordersBlock(); method(L);" in SCRIPT   # the Fill rate fold just before Orders
    f = SCRIPT.split("function ordersBlock() {")[1].split("\n}\n")[0]
    assert '[["Placed"], ["Market"], ["Side · price"], ["Asked", "num hide-sm"], ["Filled", "num"]' in f and '["Result", "num"]' in f
    assert '["At the ask", "num"]' in f                                                     # what was on offer (test_orders_at_ask.py)
    # when the order went in (a 3:08 order reads 3:08, not its window's 3:00), with its window underneath
    assert '<td class="mono">${when(o.ts)}<span class="s muted" style="display:block">${hhmm(o.ts - (o.ts % 900))}–${hhmm(o.ts - (o.ts % 900) + 900)} window</span></td>' in f
    assert "when(o.ts - (o.ts % 900))" not in f
    assert 'o.filled == null || o.filled === 0 ? "down" : o.filled >= o.asked ? "up" : "part"' in f      # none, all, or part of it
    assert "esc(o.error)" in f and "${esc(o.side)}" in f                                            # Kalshi's words, escaped
    assert "contracts filled (${pct(F.filled / F.asked, 0)})" in f and "orders got none" in f
    assert ".part { color: var(--warn-ink); }" in HTML


def study_lab(tmp_path, monkeypatch):
    """A research folder with every file the study reads."""
    monkeypatch.setattr(dashboard, "RESEARCH", str(tmp_path))
    dashboard._cache.clear()
    run = {k: None for k in dashboard.RUN_STATS} | {"curve": [240.0]}
    (tmp_path / "strategies.json").write_text(json.dumps({"t0": "2026-07-18T00:00:00+00:00", "hours": 6, "start": 240.0, "periods": [],
        "strategies": [{"id": "m8"}], "scenarios": {"live": {"m8": run}}, "starts": {"aug24": {"live": {"m8": run}}},
        "edge": {"live": {"m8": {"curve": []}}}}))
    for name in ("findings.json", "key_stats.json", "all_markets.json"):
        (tmp_path / name).write_text("{}")
    (tmp_path / "sizing.json").write_text("[]")
    feed = quiet(Exchange())                                       # the live markets, from a fake Kalshi
    feed.step(W + 60)
    monkeypatch.setattr(dashboard, "FEED", feed)


def test_the_live_board_reads_only_what_the_server_sends(tmp_path, monkeypatch):
    study_lab(tmp_path, monkeypatch)
    live_feed = dashboard.research_live()
    # the live feed (/api/research/live) is the Live tab board's now: flashOf, sparkOf and boardBlock, up to pollBoard
    assert "function flashOf(m) {" in SCRIPT and "async function pollBoard()" in SCRIPT
    board = SCRIPT.split("function flashOf(m) {")[1].split("async function pollBoard()")[0]
    market = dashboard.live()["markets"][0]
    reads = [(set(re.findall(r"\bboard\.(\w+)", board)), set(live_feed)), (set(re.findall(r"\blv\.(\w+)", board)), set(dashboard.live())),
             (set(re.findall(r"\bm\.(\w+)", board)), set(market))]
    assert all(used for used, _ in reads), "found no field reads in the board: the pattern needs updating"
    for used, sent in reads:
        assert used <= sent, f"the board reads {sorted(used - sent)}, which the feed doesn't send"
    assert {"ticker", "series", "label", "group", "open", "close", "strike", "yes_bid", "yes_ask", "volume", "oi", "favSide",
            "favPrice", "path", "book"} <= set(market)                  # every field of a market the feed has sent, it still sends


def test_the_warning_signs_are_the_bots():
    assert (bot.SPREAD_MAX, bot.LATE_MID, bot.JUMP, bot.LOOKBACK) == (0.02, 0.50, 0.10, (6, 7))


def test_the_research_tabs_have_no_live_bot_beside_them():
    """Since Oct 12 the live bot is gone from both research tabs: no sidebar, nothing that
    draws it, none of its styles and no room kept for it. The navbar (the balance, the status, Halt trading) stays on
    every tab, so the live value is still up top."""
    assert 'id="liveside"' not in HTML and '$("liveside")' not in SCRIPT
    assert not re.search(r"\bfunction liveSide\(|\bliveSide\(\)", SCRIPT)
    css = re.sub(r"/\*.*?\*/", "", HTML.split("<style>")[1].split("</style>")[0], flags=re.S)
    assert not re.search(r"\.liveside\b|\.ls-[\w-]", css) and "--ls-w" not in css
    assert not re.search(r"body\.wide \{[^}]*padding-right", css)               # Live Research gets the full width
    for nav in ('id="navBal"', 'id="navTick"', 'id="statusText"', 'id="haltTop"'):
        assert nav in HTML, nav


# ------------------------------------------------------------------ how it trades, on the Live tab
def method_script():
    return SCRIPT.split("function method(L) {")[1].split("\n}\n")[0]


def test_how_it_trades_sits_under_the_positions_and_states_every_rule():
    body = method_script()
    for rule in ("L.minute", "L.lo", "L.hi", "L.grace", "L.spreadMax", "L.lateMid", "L.jump", "L.betPct", "L.windowPct",
                 "L.orderDeadline", "L.bookMaxAge", "L.orderConnect", "L.orderAnswer", "L.ordersPerWindow", "L.ordersPerDay",
                 "L.restingEvery", "L.dayDrop", "L.windowLosses", "L.orderErrors", "L.settleLag", "L.persist", "L.limitUp",
                 "L.shadowUp"):
        assert rule in body, rule                                  # every number comes from what the server says bot.py enforces
    assert "data.groups" in body and "map(esc)" in body            # the groups, from the server, escaped
    assert "immediate-or-cancel" in body and "holds every bet to the close" in body and "python bot.py --resume" in body
    iocs = [x for x in body.split("`") if "immediate-or-cancel" in x]
    assert "L.limitUp > 0" in body                                 # the order's limit: over the ask it saw only once that's set,
    assert any("${cents(L.limitUp)}" in x for x in iocs)           # ... by that much
    assert any("at the best price it just saw on the book" in x for x in iocs)   # until then the ask it saw,
    assert "${cents(L.shadowUp)} higher" in body                   # ... and that much over it measured on paper


def test_how_it_trades_hides_with_the_account_on_the_research_tab():
    assert '"positions", "orders", "method", "more"' in SCRIPT
    assert "method(L); more(L);" in SCRIPT


def test_every_halt_the_bot_has_is_in_the_stop_list():
    stops = SCRIPT.split("const stops = [")[1].split("];")[0]
    for halt in ("L.dayDrop", "halfStart", "L.windowLosses", "L.settleLag", "Kalshi pauses trading", "Kalshi unreachable",
                 "L.orderErrors", "left resting on the book"):
        assert halt in stops, halt


def test_the_dashboard_has_no_live_markets_column():
    assert 'id="feedbar"' not in HTML and "fb-" not in HTML and "pollFeed" not in SCRIPT and "feedMk" not in SCRIPT


def test_the_live_tab_has_an_exchange_board_of_the_bots_markets_under_the_positions():
    assert HTML.index('<section id="chartPanel"') < HTML.index('<section id="positions"') < HTML.index('<section id="board" aria-label="Live markets">') < HTML.index('<section id="fills"') < HTML.index('<section id="orders"')
    assert 'for (const id of ["hero", "chartPanel", "board", "fills", "positions", "orders", "method", "more"]) $(id).hidden = other;' in SCRIPT
    b = SCRIPT.split("function boardBlock() {")[1].split("\n}\n")[0]
    assert ".filter((m) => traded.has(m.group))" in b                          # only the groups the bot trades ...
    assert "(b.favPrice ?? -1) - (a.favPrice ?? -1) || String(a.label).localeCompare(String(b.label))" in b   # ... highest first
    assert '<th scope="col" aria-sort="descending">Favorite ↓</th>' in b                  # (within each group: test_board_groups.py)
    assert 'class="bd-g"' in b and '<h3 class="bd-gh">' in b and "bd-grp" not in HTML     # a header per group, no tag per row
    for col in ("Market", "Favorite ↓", "Bid", "Ask", "Spread", "This window", "Trend"):
        assert f'<th scope="col"' in b and f">{col}</th>" in b, col
    assert '<td class="hide-sm">${cents(bid)}</td><td class="hide-sm">${cents(ask)}</td>' in b   # a phone keeps market, price, change
    assert 'm.favSide === "no" ? [m.yes_ask == null ? null : 1 - m.yes_ask' in b                # a NO favorite's bid and ask, from YES's
    assert '<span class="bd-in" title="In the bot\'s ${cents(lo)}–${cents(hi)} buying range">In range</span>' in b   # in words, not only the edge
    assert '(stream ? ["on", "Streaming"] : ["warn", "Polling"])' in b and "esc(why)" in b and "esc(m.label)" in b


def test_the_board_streams_while_the_live_tab_is_on_screen_and_flashes_each_change_with_an_arrow():
    assert "const BOARD_EVERY = 250;" in SCRIPT and "setInterval(pollBoard, BOARD_EVERY);" in SCRIPT
    assert 'if (boardBusy || document.hidden || page !== "account") return;' in SCRIPT     # the Research tabs read their own
    assert 'fetch("/api/research/live", { cache: "no-store" })' in SCRIPT
    assert dashboard.RESEARCH_EVERY <= 0.25                          # the live feed's cache stays under the board's 250 ms poll
    assert 'class="bd-r${inRange ? " in" : ""}${fl ? " fl-" + fl : ""}"' in SCRIPT and "function flashOf(m)" in SCRIPT
    assert '${fl === "up" ? "▲" : fl === "down" ? "▼" : "⇄"}</i>' in SCRIPT                   # an arrow as well as the colour
    assert "@media (prefers-reduced-motion: reduce) { .bd-r.fl-up td, .bd-r.fl-down td, .bd-r.fl-flip td { animation: none; } }" in HTML
    assert ".bd-t td.up { color: var(--up-ink); }" in HTML                      # the change keeps its colour inside the board


def test_a_market_on_the_board_links_to_it_on_kalshi():
    """Historical Research has no Markets view to open any more, so a market's name opens its page on Kalshi, in a new tab."""
    b = SCRIPT.split("function boardBlock() {")[1].split("\n}\n")[0]
    assert ('<td><a class="bd-mk" href="${esc(kalshiUrl(m.ticker))}" target="_blank" rel="noopener" '
            'title="${esc(m.label)} on Kalshi">${esc(m.label)}</a>') in b
    assert "data-board-mk" not in HTML and "boardMk" not in SCRIPT                  # no click on it opens a research tab ...
    assert "researchOpen" not in HTML, "dashboard.html still mentions researchOpen"   # ... and nothing is left to open one
    assert re.search(r"\.bd-mk \{[^}]*\btext-decoration: none\b", HTML)           # a link now: plain until hovered
    assert ".bd-mk:hover { text-decoration: underline; }" in HTML
    assert dashboard.QUOTES_EVERY == 1                                          # polling, when it must, is once a second


def test_the_page_is_full_width_and_a_wide_screen_puts_the_account_beside_its_chart():
    assert ":root { --gutter: clamp(16px, 3vw, 40px); }" in HTML
    assert ".top-in { max-width: none;" in HTML and ".wrap { max-width: none;" in HTML        # the header and page span the window
    wide = HTML.split("@media (min-width: 1100px) {")[1].split("\n}")[0]
    assert "body:not(.wide) .wrap { grid-template-columns: minmax(320px, 1fr) minmax(0, 2.2fr);" in wide
    assert "body:not(.wide) #hero { grid-column: 1; }" in wide and "body:not(.wide) #chartPanel { grid-column: 2; }" in wide
    assert "body:not(.wide) .wrap > * { grid-column: 1 / -1; }" in wide                      # everything else across the page
    assert ".method { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));" in wide   # no line of rules runs too long
    # the orders sit flush in their fold, which is their panel (as the board's): no box of their own inside it
    assert "#orders .fold-body > .table-wrap { margin-top: 0; border: 0; border-radius: 0; }" in HTML
    assert "#orders .table-wrap { margin-top: 12px; border: 1px solid var(--line)" not in HTML

