"""The balance in the navbar: /api/balance reads it from Kalshi once a second, and the page draws it with the change
since the start, or the change alone when you hide the balance.

The server side runs dashboard.balance_now() and the route against the stubbed Kalshi client of
test_dashboard_more.py. The page side cuts navBalance() and the helpers it uses out of dashboard.html and runs them in
node (skipped without node), reading the HTML it writes into the navbar.
    python -m pytest tests/test_navbar_balance.py -q
"""

import json
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, fetch, home, kalshi_stub, mode_db, serving, with_cfg  # noqa: F401 (fixtures)

PROD = dict(KALSHI_ENV="prod", KALSHI_API_KEY_ID="id", KALSHI_PRIVATE_KEY_PATH="/k.pem")


# ------------------------------------------------------------------ the server: a fresh Kalshi read for every 1-second poll
def test_every_one_second_poll_gets_a_fresh_read_even_though_kalshi_takes_a_while(home, kalshi_stub, monkeypatch):
    # The cache stamps a reading when Kalshi's answer arrives (~0.3-0.6 s after asking), so with a 1-second cache the
    # page's next poll, 1 s after the last one asked, landed inside it: every other poll got the old reading, and the
    # balance moved every 2 seconds. Measured on the live page on Oct 10: 12 polls, 6 Kalshi reads.
    mode_db(home, "live-prod")
    with_cfg(monkeypatch, **PROD)
    slow = kalshi_stub.balance

    def balance(self):
        home.clock[0] += 0.4                            # the call takes 0.4 s
        return slow(self)
    monkeypatch.setattr(kalshi_stub, "balance", balance)
    with serving() as base:
        asked = home.clock[0]
        for n in range(1, 6):
            fetch(base, "/api/balance")
            assert len(kalshi_stub.instances) == n      # every poll a new read
            home.clock[0] = asked + n                   # the page asks again 1 s after it last asked


def test_the_balance_is_cash_plus_open_positions_and_the_gain_is_measured_from_the_start(home, kalshi_stub, monkeypatch):
    mode_db(home, "live-prod", start=500.0)
    with_cfg(monkeypatch, **PROD)
    kalshi_stub.bal = {"balance": 51773, "balance_dollars": "512.5541", "portfolio_value": 518, "updated_ts": 1791652844}
    got = dashboard.balance_now("live-prod")
    assert got["value"] == pytest.approx(517.7341)              # $512.5541 cash + $5.18 Kalshi values the open positions at
    assert got["gain"] == pytest.approx(17.7341)                # the start already takes in deposits (bot.rebase)
    assert got["pct"] == pytest.approx(17.7341 / 500)
    assert (got["now"], got["updated"]) == (NOW, 1791652844)
    assert kalshi_stub.instances[0].args == ("prod", "id", "/k.pem")


def test_it_makes_only_the_one_balance_call(home, kalshi_stub, monkeypatch):
    mode_db(home, "live-prod", start=100.0)
    with_cfg(monkeypatch, **PROD)

    def no(*a, **k):
        raise AssertionError("the navbar's balance must cost one Kalshi call")
    for name in ("positions", "exchange_status", "get", "markets"):
        monkeypatch.setattr(kalshi_stub, name, no)
    assert dashboard.balance_now("live-prod")["value"] == pytest.approx(50.0)


def test_with_no_start_yet_there_is_no_percentage(home, kalshi_stub, monkeypatch):
    mode_db(home, "live-prod", start=None)
    with_cfg(monkeypatch, **PROD)
    got = dashboard.balance_now("live-prod")
    assert got["value"] == pytest.approx(50.0) and got["pct"] is None


def test_it_says_why_when_it_cant_read_the_balance(home, kalshi_stub, monkeypatch):
    mode_db(home, "live-prod")
    with_cfg(monkeypatch)
    assert dashboard.balance_now("live-prod") == {"error": "no API key in .env"}
    with_cfg(monkeypatch, **PROD)
    kalshi_stub.bal, kalshi_stub.last_error = None, "HTTP 401: bad key"
    assert dashboard.balance_now("live-prod") == {"error": "HTTP 401: bad key"}
    kalshi_stub.bal, kalshi_stub.last_error = {"oops": 1}, None
    assert dashboard.balance_now("live-prod") == {"error": "couldn't read the balance"}


def test_the_route_serves_the_chosen_live_account_and_falls_back_to_the_first(home, kalshi_stub, monkeypatch):
    mode_db(home, "live-prod", start=40.0)
    mode_db(home, "live-demo", start=25.0)
    with_cfg(monkeypatch, **PROD)
    with serving() as base:
        status, headers, body = fetch(base, "/api/balance")
        assert status == 200 and headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
        assert json.loads(body)["gain"] == pytest.approx(10.0)                    # live-prod: $50 against a $40 start
        assert json.loads(fetch(base, "/api/balance?mode=live-demo")[2]) == {"error": "the key in .env is for prod, not demo"}
        for bad in ("nope", "../../etc/passwd", "dry-prod"):
            assert json.loads(fetch(base, f"/api/balance?mode={bad}")[2])["gain"] == pytest.approx(10.0)


def test_tabs_polling_together_share_one_read(home, kalshi_stub, monkeypatch):
    assert dashboard.BALANCE_EVERY == 0.5               # under the page's 1-second poll, as RESEARCH_EVERY is under its
    mode_db(home, "live-prod")
    with_cfg(monkeypatch, **PROD)
    with serving() as base:
        for _ in range(3):
            fetch(base, "/api/balance")
        assert len(kalshi_stub.instances) == 1          # three tabs polling at once: one call to Kalshi (two a second at most)
        home.clock[0] += 0.5
        fetch(base, "/api/balance")
        assert len(kalshi_stub.instances) == 2


def test_with_no_live_account_the_route_says_so(home):
    with serving() as base:
        assert json.loads(fetch(base, "/api/balance")[2]) == {"error": "no live account yet"}


# ------------------------------------------------------------------ the page: the navbar, run in node
HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def harness():
    return "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "nf", "zero", "money", "spct", "tone", "arrow", "eyeIcon")),   # one line each
        piece(r"^function navBalance\(\) \{.*?^\}$"),
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "let bal = input.bal, balStale = !!input.stale, hideBal = !!input.hide, html = null, stale = null;",
        "const patch = (id, h) => { if (id === 'navBal') html = h; };",
        "const $ = (id) => ({ classList: { toggle: (c, on) => { if (c === 'stale') stale = on; } } });",
        "navBalance();",
        "process.stdout.write(JSON.stringify({ html, stale }));",
    ])


def draw(bal, hide=False, stale=False):
    r = subprocess.run([NODE, "-e", harness()], input=json.dumps({"bal": bal, "hide": hide, "stale": stale}),
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


UP = {"value": 517.7341, "gain": 17.7341, "pct": 0.0354682, "now": NOW}


@needs_node
def test_the_navbar_shows_the_balance_and_the_change_since_the_start():
    html = draw(UP)["html"]
    assert "$517.73" in html and "+3.5%" in html
    assert 'class="nb-p up"' in html and "▲" in html                     # a gain: green, with a sign and an arrow


@needs_node
def test_a_loss_reads_as_one():
    html = draw({**UP, "value": 480.0, "gain": -20.0, "pct": -0.04})["html"]
    assert "$480.00" in html and "−4.0%" in html and 'class="nb-p down"' in html and "▼" in html


@needs_node
def test_hiding_the_balance_keeps_the_percentage():
    html = draw(UP, hide=True)["html"]
    assert "$" not in html and "517" not in html                          # no dollar figure anywhere, the title included
    assert "+3.5%" in html


@needs_node
def test_the_toggle_is_a_labelled_button_that_says_whether_it_is_on():
    shown, hidden = draw(UP)["html"], draw(UP, hide=True)["html"]
    for html, pressed, verb in ((shown, "false", "Hide"), (hidden, "true", "Show")):
        assert re.search(rf'<button class="eye" type="button" data-bal="nav" aria-pressed="{pressed}" aria-label="Hide balance" title="{verb} balance">', html)


@needs_node
def test_nothing_shows_before_the_first_reading_and_an_old_one_is_dimmed():
    assert draw(None)["html"] == ""
    assert draw({"error": "no live account yet"})["html"] == ""
    assert draw(UP, stale=True)["stale"] is True and draw(UP)["stale"] is False


@needs_node
def test_no_start_yet_shows_the_balance_without_a_percentage():
    html = draw({**UP, "pct": None})["html"]
    assert "$517.73" in html and "%" not in html


def test_the_page_polls_the_balance_every_second_without_piling_up_requests():
    assert re.search(r"^const BALANCE_EVERY = 1000;", HTML, re.M)
    assert re.search(r"^setInterval\(pollBalance, BALANCE_EVERY\);$", HTML, re.M)
    poll = piece(r"^async function pollBalance\(\) \{.*?^\}$")
    assert 'fetch("/api/balance' in poll and "balBusy" in poll   # one request at a time: a slow answer never stacks up


def test_the_navbar_has_a_place_for_it_and_the_toggle_shares_the_heros_setting():
    top = piece(r'<header class="top">.*?</header>')
    assert '<span id="navBal" class="navbal"' in top
    # one "hide balance" setting for the page: the navbar's eye flips the same hideBal the hero's does, and keeps focus
    assert re.search(r'else if \("bal" in t\.dataset\) \{.*?hideBal = !hideBal;.*?navBalance\(\);.*?\$\(t\.dataset\.bal === "nav" \? "navBal" : "hero"\)', HTML, re.S)


def test_the_footer_says_the_balance_refreshes_every_second():
    assert "the balance up top every second" in HTML and "your Kalshi balance every 10" not in HTML


def test_on_a_phone_the_balance_stacks_so_the_halt_button_stays_in_view():
    # side by side it pushed "Halt trading" off a 390px screen: under 560px the dollars sit over the %, and under 400px
    # the navbar's eye goes (as the theme button does; the hero keeps its own)
    phone = piece(r"^@media \(max-width: 560px\) \{.*?^\}$")
    assert re.search(r"\.navbal \{[^}]*grid-template-rows: auto auto;", phone)
    assert re.search(r"\.navbal \.eye \{[^}]*grid-row: span 2;", phone)
    assert re.search(r"^@media \(max-width: 400px\) \{[^\n]*\.navbal \.eye \{ display: none; \}", HTML, re.M)


# ------------------------------------------------------------------ proof it's polling: a dot that blinks per fresh read
def tick_harness():
    return "\n".join([
        piece(r"^const hms = [^\n]*$"),
        piece(r"^function patch\(id, html\) \{.*?^\}$"), piece(r"^function noteRead\(t\) \{.*?^\}$"), piece(r"^function navTick\(\) \{.*?^\}$"),
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "const shown = new Map(); let bal = null, balStale = false, balReads = [], writes = 0, inner = '';",
        "const el = { title: '', set innerHTML(h) { inner = h; writes++; }, get innerHTML() { return inner; } };",
        "const $ = (id) => id === 'navTick' ? el : null;",
        "const out = [];",
        "for (const s of input.steps) {",
        "  bal = s.bal; balStale = !!s.stale;",
        "  if (bal && !balStale) noteRead(bal.now);",
        "  navTick();",
        "  out.push({ html: el.innerHTML, title: el.title, writes });",
        "}",
        "process.stdout.write(JSON.stringify(out));",
    ])


def ticks(*steps):
    import os
    r = subprocess.run([NODE, "-e", tick_harness()], input=json.dumps({"steps": list(steps)}), capture_output=True, text=True,
                       encoding="utf-8", timeout=30, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def reading(t):
    return {**UP, "now": t}


@needs_node
def test_nothing_ticks_before_the_first_reading():
    last = ticks({"bal": None}, {"bal": {"error": "no live account yet"}})[-1]
    assert (last["html"], last["title"]) == ("", "")


@needs_node
def test_each_reading_shows_its_time_to_the_second():
    (got,) = ticks({"bal": reading(NOW + 5)})                       # NOW is 3 pm in New York
    assert 'class="nb-dot"' in got["html"] and "3:00:05" in got["html"]
    assert "Read from Kalshi at 3:00:05" in got["title"] and "1 read in the last minute" in got["title"]


@needs_node
def test_every_fresh_reading_redraws_the_dot_so_it_blinks_and_a_repeat_does_not():
    got = ticks({"bal": reading(NOW)}, {"bal": reading(NOW)},               # the same reading again (another tab's): no blink
                {"bal": reading(NOW + 0.97)},                              # a fresh one in the same clock second: still a blink
                {"bal": reading(NOW + 2)})
    assert [g["writes"] for g in got] == [1, 1, 2, 3]


@needs_node
def test_the_hover_counts_the_reads_in_the_last_minute():
    got = ticks(*({"bal": reading(NOW + i)} for i in range(75)))            # 75 polls, a second apart
    assert "60 reads in the last minute" in got[-1]["title"]                # about 60 when it's polling every second


@needs_node
def test_when_kalshi_stops_answering_the_dot_turns_red_and_still():
    got = ticks({"bal": reading(NOW)}, {"bal": reading(NOW), "stale": True})
    assert 'class="nb-dot stale"' in got[-1]["html"] and got[-1]["title"].startswith("Kalshi didn't answer the last poll.")


def test_the_dot_blinks_by_css_and_still_blinks_with_reduced_motion():
    assert re.search(r"^\.nb-dot \{[^}]*animation: nb-blink ", HTML, re.M) and "@keyframes nb-blink" in HTML
    assert re.search(r"^\.nb-dot\.stale \{[^}]*animation: none;[^}]*var\(--down\)", HTML, re.M)
    # the point of it is to blink: with reduced motion it steps on and off instead of fading, and nothing moves either way
    assert re.search(r"@media \(prefers-reduced-motion: reduce\) \{ \.nb-dot \{ animation-timing-function: steps\(1, end\); \} \}", HTML)
    assert "scale" not in piece(r"^@keyframes nb-blink \{[^\n]*$")


def test_the_tick_sits_in_the_navbar_and_poll_drives_it():
    top = piece(r'<header class="top">.*?</header>')
    assert re.search(r'<span id="navTick" class="nb-tick"></span>\s*<span id="navBal"', top)
    poll = piece(r"^async function pollBalance\(\) \{.*?^\}$")
    assert "noteRead(b.now)" in poll and "navTick();" in poll
    assert re.search(r"\.nb-t \{ display: none; \}", piece(r"^@media \(max-width: 560px\) \{.*?^\}$"))   # a phone: the dot alone
