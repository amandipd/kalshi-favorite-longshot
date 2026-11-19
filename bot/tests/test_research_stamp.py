"""The worst 24 hours reaching /api/research, the route's cheap check for a newer study, and the Live tab's market board
linking each market to Kalshi. (The Historical Research tab that drew them left the page on Oct 15; the routes stay.)

The backtest (strategies_backtest.py) gives every run its worst 24 hours: "worst24hPct", the deepest fall from a high
within any 24 hours as a share of that high (what the live bot's 35% halt watches), "worst24h", that fall in dollars,
and "worst24hAt", when it bottomed out (None when it never fell). They join RUN_STATS, the stats replay() hands the page
for every run, along with "liveFit" (each live-fills run's orders and contracts), which was left out, so the "Filled like
live orders" panel never reached the page. A strategies.json from before them gives None for each.

The tab no longer polls the live feed once a second to learn when the research changed. It asks GET /api/research/stamp
at most every 5 seconds instead: {"stamp": stamp()}, when the research files last changed, and fetches the whole study
(/api/research) only when that moves. Answering only looks at when the files changed, never at what's in them, and never
wakes the live feed (it reads Kalshi only while someone watches it, FEED.watched).

The tab's Markets view is gone, so a market's name on the Live tab's board no longer opens it: it links to that market
on Kalshi, in a new tab, and still looks like a name until it's hovered.

Nothing here touches the network or the real research files.

    python -m pytest tests/test_research_stamp.py -q
"""
import builtins
import json
import re
import types

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, fetch, lab, serving, write  # noqa: F401 (lab is a fixture pytest finds by name)

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NEW = ("worst24h", "worst24hPct", "worst24hAt", "liveFit")
WORST = {"worst24h": -84.12, "worst24hPct": -0.2875, "worst24hAt": "2026-08-02T13:45:00+00:00"}
NEVER_FELL = {"worst24h": 0.0, "worst24hPct": 0.0, "worst24hAt": None}
FIT = {"orders": 210, "asked": 8890.5, "got": 2585.25, "missed": 0}


def old_run(final):
    """A run as a strategies.json from before the worst-24-hours fields has it."""
    return {"start": 240.0, "final": final, "ret": final / 240.0 - 1, "broke": None, "bets": 10, "wins": 9, "winRate": 0.9,
            "need": 0.95, "perBet": 1.5, "maxDD": 0.2, "worstWindow": -9.0, "worstWindowPct": -0.04, "worstDay": -20.0,
            "losingDays": 1, "days": 3, "byGroup": [], "byBand": [], "bySeries": [], "periods": {}, "exit": None,
            "liquidity": None, "curve": [240.0] * 30}


def strategies(old=False):
    """A strategies.json with three accounts (the live bot, its live-fills twin and one that never fell) under both fill
    assumptions, from Jul 18 (scenarios) and from Dec 10 and Aug 24 (starts). old=True writes every run as a backtest
    from before the new fields did."""
    def accounts(final):
        if old:
            return {sid: old_run(final + i) for i, sid in enumerate(("m8", "livefit", "flat"))}
        return {"m8": {**old_run(final), **WORST, "liveFit": None},
                "livefit": {**old_run(final + 1), **WORST, "liveFit": FIT},
                "flat": {**old_run(final + 2), **NEVER_FELL, "liveFit": None}}
    return {"t0": "2025-12-10T00:00:00+00:00", "hours": 30, "start": 240.0, "periods": [],
            "strategies": [{"id": "m8", "name": "The live bot"}, {"id": "livefit", "name": "The live bot · live fills", "liveFit": True},
                           {"id": "flat", "name": "Never fell"}],
            "scenarios": {"live": accounts(700.0), "backtest": accounts(800.0)},
            "starts": {s: {"live": accounts(300.0), "backtest": accounts(310.0)} for s in ("dec10", "aug24")}}


def every_run(replay):
    return [((fills, start, sid), r) for fills, starts in replay["runs"].items() for start, rows in starts.items() for sid, r in rows.items()]


# ------------------------------------------------------------------ the worst 24 hours, and live fills, reach the page
def test_every_run_hands_on_its_worst_24_hours_and_its_live_fills():
    assert set(NEW) <= set(dashboard.RUN_STATS), sorted(set(NEW) - set(dashboard.RUN_STATS))
    kept = ("start", "final", "ret", "broke", "bets", "wins", "winRate", "need", "perBet", "maxDD", "worstWindow", "worstWindowPct",
            "worstDay", "losingDays", "days", "byGroup", "byBand", "bySeries", "periods", "exit", "liquidity")
    assert set(kept) <= set(dashboard.RUN_STATS)                                  # added to, nothing dropped


def test_the_replay_carries_them_for_every_fill_assumption_and_start(lab):
    write(lab, "strategies.json", strategies())
    runs = every_run(dashboard.replay())
    assert {where[:2] for where, _ in runs} == {(f, s) for f in ("live", "backtest") for s in ("jul18", "dec10", "aug24")}
    for (fills, start, sid), r in runs:
        assert {k: r.get(k) for k in WORST} == (NEVER_FELL if sid == "flat" else WORST), (fills, start, sid)
        assert r.get("liveFit") == (FIT if sid == "livefit" else None), (fills, start, sid)


def test_the_research_route_carries_them(lab):
    write(lab, "strategies.json", strategies())
    with serving() as base:
        status, _, body = fetch(base, "/api/research")
    r = json.loads(body)["replay"]["runs"]["live"]["jul18"]
    assert status == 200
    assert {k: r["m8"].get(k) for k in WORST} == WORST and r["livefit"].get("liveFit") == FIT
    assert {k: r["flat"].get(k) for k in WORST} == NEVER_FELL                     # a run that never fell: 0, and no date


def test_a_backtest_from_before_them_gives_none(lab):
    write(lab, "strategies.json", strategies(old=True))
    for where, r in every_run(dashboard.replay()):
        assert set(NEW) <= set(r), (where, sorted(set(NEW) - set(r)))           # the page finds each field, empty
        assert {k: r[k] for k in NEW} == dict.fromkeys(NEW), where


# ------------------------------------------------------------------ GET /api/research/stamp
@pytest.fixture
def desk(lab, monkeypatch):
    """lab's empty research folder, with a clock the test moves on between asks (the page asks at most every 5 seconds)."""
    clock = [NOW]
    monkeypatch.setattr(dashboard, "time", types.SimpleNamespace(time=lambda: clock[0]))
    return types.SimpleNamespace(dir=lab, clock=clock)


def stamp_of(base):
    status, headers, body = fetch(base, "/api/research/stamp")
    assert status == 200, f"HTTP {status} {body[:200]!r}"
    assert headers["Content-Type"] == "application/json" and headers["Cache-Control"] == "no-store"
    return json.loads(body)


def test_the_stamp_route_answers_with_the_studys_stamp_and_nothing_else(desk):
    with serving() as base:
        empty = stamp_of(base)
        write(desk.dir, "findings.json", {}, mtime=1000)
        write(desk.dir, "sizing.json", [], mtime=3000)
        write(desk.dir, "strategies.json", strategies(), mtime=2000)
        desk.clock[0] += 30
        got = stamp_of(base)
    assert empty == {"stamp": 0}                                                   # no study yet
    assert got == {"stamp": dashboard.stamp()} == {"stamp": 3000}


def test_the_stamp_moves_when_a_study_file_changes_and_only_then(desk):
    write(desk.dir, "findings.json", {"v": 1}, mtime=1000)
    seen = []
    with serving() as base:
        for change in (None,                                                       # asked again, nothing changed
                       ("unrelated.json", {}, 9000),                               # not a file the tab reads
                       ("findings.json", {"v": 2}, 2000),
                       ("strategies.json", strategies(), 5000),
                       ("dashboard/src/generated/dashboard.json", {}, 6000)):
            seen.append(stamp_of(base)["stamp"])
            if change:
                write(desk.dir, *change[:2], mtime=change[2])
            desk.clock[0] += 30
        seen.append(stamp_of(base)["stamp"])
    assert seen == [1000, 1000, 1000, 2000, 5000, 6000]


def test_the_stamp_route_reads_no_study_file(desk, monkeypatch):
    """Only when the files changed, never what's in them: a corrupt strategies.json still has a stamp, and nothing is
    opened or parsed (the whole study is /api/research's job, and only when this moves)."""
    write(desk.dir, "findings.json", {"v": 1}, mtime=1000)
    write(desk.dir, "strategies.json", "{not json", mtime=4000)
    reads = []
    monkeypatch.setattr(dashboard, "open", lambda *a, **k: reads.append(a[0]) or builtins.open(*a, **k), raising=False)
    monkeypatch.setattr(dashboard, "read_json", lambda path: reads.append(path))
    monkeypatch.setattr(dashboard, "study", lambda: reads.append("study()") or {})
    with serving() as base:
        got = stamp_of(base)
    assert got == {"stamp": 4000}
    assert reads == []


def test_the_stamp_route_never_wakes_the_live_feed(desk):
    feed = dashboard.FEED
    write(desk.dir, "findings.json", {}, mtime=1000)
    with serving() as base:
        stamp_of(base)
        assert (feed.watched, feed.k.calls) == (0.0, [])                          # not watched, Kalshi never asked
        desk.clock[0] += 30
        fetch(base, "/api/research/live")                                         # the board's route does watch it ...
    assert feed.watched == NOW + 30                                                # ... so the check above could see a wake


# ------------------------------------------------------------------ the Live tab's board links each market to Kalshi
def board():
    script = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)
    assert "function boardBlock() {" in script, "the board's code moved: update this test"
    return script.split("function boardBlock() {")[1].split("\n}\n")[0]


def test_a_market_on_the_board_links_to_it_on_kalshi_in_a_new_tab():
    assert ('<td><a class="bd-mk" href="${esc(kalshiUrl(m.ticker))}" target="_blank" rel="noopener" title="${esc(m.label)} on Kalshi">'
            '${esc(m.label)}</a>') in board()


def test_nothing_on_the_page_opens_the_research_markets_view_any_more():
    assert "data-board-mk" not in HTML
    assert "boardMk" not in HTML                                                   # the click branch went with it
    assert "researchOpen" not in HTML


def test_the_market_link_looks_like_a_name_until_hovered():
    rule = re.search(r"^\.bd-mk \{([^}]*)\}", HTML, re.M)
    assert rule, "no .bd-mk rule"
    assert "text-decoration: none" in rule.group(1)
    assert ".bd-mk:hover { text-decoration: underline; }" in HTML
