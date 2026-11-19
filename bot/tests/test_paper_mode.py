"""The dashboard tracks the paper bot only, and stops showing the real Kalshi account, once a paper ledger exists.

- modes() lists the paper ledgers (dry-prod; not a dated experiment copy like dry-prod-500-nov3, and not a --paper
  account), and the old live modes only while no paper ledger exists, so old data still renders.
- /api/state for a dry mode sends no "kalshi" and no "kalshiCurve" (nothing on the page can show the wallet), and a
  "sim" instead: the mine4liq1k account out of the research backtest (strategies.json, starts.dec10.live), the
  simulated $1,000 replayed on real prices and real book depth since Dec 10, 2025, with its bankroll every
  REPLAY_STEP hours; None while the backtest or the run is missing.
- /api/balance for a dry mode never asks Kalshi: the sim's value, marked "paper": true, or the dry ledger's own
  bankroll while there's no sim.
- The page: the dry-prod tab reads "Paper"; the hero leads with the sim's value, its "Started with ... Profit ..."
  line and one muted "Simulated $1,000 since ..." line, with no "Live from Kalshi" line; the bankroll chart draws the
  sim's curve; the navbar's balance carries a PAPER chip. The Won/Lost tiles and the folds keep the dry ledger's own
  numbers. A state without a sim draws as it always did, so the golden fixtures stand.

The server side runs against the home fixture of test_dashboard_more.py; the page side is test_folds_live.py's
stand-in browser and test_navbar_balance.py's navbar harness (both skipped without node).
    python -m pytest tests/test_paper_mode.py -q
"""
import json

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, add_bet, fetch, home, mode_db, serving  # noqa: F401  (home is a fixture)
from test_folds_live import golden, js, needs_node, run
from test_navbar_balance import UP, draw

T0 = "2025-12-10T00:00:00+00:00"   # midnight UTC, as strategies.json writes it: still Dec 9 in New York (the tests' TZ)
CURVE = [None] * 6 + [1000.0 + 10.0 * i for i in range(25)]   # hourly from t0; thinned by REPLAY_STEP for the page
THINNED = [None, 1000.0, 1060.0, 1120.0, 1180.0, 1240.0]
RUN = {"start": 1000.0, "final": 1240.0, "ret": 0.24, "bets": 4200, "wins": 4005, "maxDD": 0.18, "curve": CURVE,
       "winRate": 0.9536, "need": 0.9412}
SIM = {"start": 1000.0, "value": 1240.0, "ret": 0.24, "bets": 4200, "wins": 4005, "maxDD": 0.18,
       "curve": THINNED, "t0": T0, "hours": 30, "step": 6, "winRate": 0.9536, "need": 0.9412,
       "groups": [], "markets": []}   # RUN has no byGroup / bySeries: no first bets to mark


@pytest.fixture
def lab(home, tmp_path_factory, monkeypatch):
    """An empty research folder of this test's own: no backtest until the test writes one."""
    folder = tmp_path_factory.mktemp("research")
    monkeypatch.setattr(dashboard, "RESEARCH", str(folder))
    dashboard._cache.clear()
    return folder


def write_study(folder, run=RUN):
    """strategies.json with the simulated $1,000 account beside the real-money one, as strategies_backtest.py writes it."""
    (folder / "strategies.json").write_text(json.dumps({
        "t0": T0, "hours": 30, "start": 240.0, "periods": [],
        "strategies": [{"id": "mine4liq"}],
        "scenarios": {"live": {"mine4liq": {"start": 2000.0, "final": 2100.0, "curve": [2000.0]}}},
        "starts": {"dec10": {"live": {"mine4liq1k": run,
                                      "mine4liq": {"start": 2000.0, "final": 2222.0, "curve": [2000.0]}}}},
        "edge": {}}), encoding="utf-8")
    dashboard._cache.clear()


def never_kalshi(monkeypatch):
    def no(*a, **k):
        raise AssertionError("a paper mode must never ask Kalshi")
    monkeypatch.setattr(dashboard, "client", no)


# ------------------------------------------------------------------ modes: the paper ledger replaces the live tabs
def test_a_paper_ledger_takes_the_live_tabs_off_the_page(home):
    for name in ("live-demo", "live-prod", "paper-prod", "dry-prod-500-nov3"):
        mode_db(home, name)
    assert dashboard.modes() == ["live-prod", "live-demo"]     # no paper ledger yet: old data still renders
    mode_db(home, "dry-demo")
    mode_db(home, "dry-prod")
    assert dashboard.modes() == ["dry-prod", "dry-demo"]       # dated experiment copies and --paper accounts get no tab


# ------------------------------------------------------------------ /api/state: the sim in, the wallet out
def test_a_paper_state_sends_the_sim_and_never_the_wallet(home, lab):
    write_study(lab)
    db = mode_db(home, "dry-prod", start=100.0)
    add_bet(db, "KXBTC15M-1", status="won")
    s = dashboard.state("dry-prod")
    assert "kalshi" not in s and "kalshiCurve" not in s        # nothing of the real account reaches the page
    assert s["sim"] == SIM
    assert home.calls["account"] == [] and home.calls["history"] == []


def test_the_sim_is_none_while_the_backtest_or_the_run_is_missing(home, lab):
    mode_db(home, "dry-prod")
    assert dashboard.state("dry-prod")["sim"] is None          # no strategies.json yet
    write_study(lab, run="not a run")
    assert dashboard.state("dry-prod")["sim"] is None          # the run isn't there (or isn't a run)


def test_a_live_state_still_sends_the_wallet_and_no_sim(home, lab):
    write_study(lab)
    mode_db(home, "live-prod")
    s = dashboard.state("live-prod")
    assert "sim" not in s and s["kalshi"] == {"total": 50.0, "crypto": 40.0, "positions": 1}


# ------------------------------------------------------------------ /api/balance: no Kalshi call for a paper mode
def test_the_paper_balance_is_the_sims_with_no_kalshi_call(home, lab, monkeypatch):
    write_study(lab)
    mode_db(home, "dry-prod", start=100.0)
    never_kalshi(monkeypatch)
    got = dashboard.balance_now("dry-prod")
    assert got["value"] == 1240.0 and got["gain"] == 240.0 and got["pct"] == pytest.approx(0.24)
    assert got["paper"] is True and got["now"] == NOW
    assert got["updated"] == dashboard.stamp()                 # the sim moves only when the research outputs do


def test_without_a_sim_the_paper_balance_is_the_ledgers_own_bankroll(home, lab, monkeypatch):
    db = mode_db(home, "dry-prod", start=100.0)
    add_bet(db, "KXBTC15M-1", price=0.95, contracts=3, status="won", fee=0.01)   # +0.14
    never_kalshi(monkeypatch)
    got = dashboard.balance_now("dry-prod")
    assert got["value"] == pytest.approx(100.14) and got["gain"] == pytest.approx(0.14)
    assert got["paper"] is True and got["updated"] is None


def test_the_balance_route_serves_the_paper_mode(home, lab):
    write_study(lab)
    mode_db(home, "live-prod", start=40.0)
    mode_db(home, "dry-prod", start=100.0)
    with serving() as base:
        got = json.loads(fetch(base, "/api/balance")[2])
        assert got["paper"] is True and got["value"] == 1240.0
        # the live tabs are gone while a paper ledger exists: a live name falls back to the paper mode
        assert json.loads(fetch(base, "/api/balance?mode=live-prod")[2])["paper"] is True


# ------------------------------------------------------------------ the page: the hero, the chart and the navbar
def dry_inputs(**over):
    """The golden Live tab data turned into a paper mode's: no kalshi, no kalshiCurve, a sim."""
    g = golden()
    st = {k: v for k, v in g["state"].items() if k not in ("kalshi", "kalshiCurve")}
    st.update({"mode": "dry-prod", "modes": ["dry-prod"], "live": False, "sim": SIM, **over})
    return {"now": g["now"], "state": st, "board": g["board"]}


def hero_text(page):
    return " ".join("".join(page.by_id("hero").texts()).split())


@needs_node
def test_the_dry_prod_tab_reads_paper():
    assert js('label("dry-prod")') == "Paper"
    assert js('label("live-prod")') == "Live"


@needs_node
def test_the_paper_hero_leads_with_the_sim():
    text = hero_text(run(inputs=dry_inputs())[0])
    assert "Portfolio · Paper" in text
    assert "$1,240.00" in text                                               # the headline is the sim's value
    assert "Started with $1,000.00 · Profit ▲ +$240.00 (+24.0%)" in text
    assert "Simulated $1,000 since Dec 10, 2025 · replayed on real prices and real book depth" in text
    assert "Live from Kalshi" not in text and "From the bot's books" not in text
    assert "Staked" not in text              # the dry ledger's staked line would read as the sim's
    assert "Won" in text and "Lost" in text


@needs_node
def test_without_a_sim_the_paper_hero_is_the_ledgers_as_before():
    text = hero_text(run(inputs=dry_inputs(sim=None))[0])
    assert "From the bot's books" in text and "Simulated" not in text


@needs_node
def test_hiding_the_balance_keeps_the_sims_percentage():
    text = hero_text(run(store={"hideBal": "1"}, inputs=dry_inputs())[0])
    assert "+24.0%" in text and "$" not in text


@needs_node
def test_the_paper_chart_draws_the_sims_curve():
    p = run(inputs=dry_inputs())[0]
    svg = next(e for e in p.by_id("chart").els() if e.tag == "svg")
    assert svg.attrs["aria-label"].startswith("The simulated account's value, from $1,000.00 to $1,240.00.")
    assert [e.text() for e in svg.els() if e.has_class("valtxt")] == ["$1,240.00"]
    assert len([e for e in svg.els() if e.has_class("ln")]) == 1             # one line, from the sim's points


@needs_node
def test_the_navbar_marks_a_paper_balance_with_a_chip():
    html = draw({**UP, "paper": True})["html"]
    assert 'class="chip"' in html and ">Paper<" in html and "$517.73" in html
    assert "chip" not in draw(UP)["html"]                                    # a live balance carries no chip


# ------------------------------------------------------------------ the scoreboard follows the headline (Nov 5)
@needs_node
def test_with_a_sim_the_scoreboard_is_the_sims_record_not_the_paper_bots():
    """The tiles sit straight under "$1,000 since Dec 10", so they must be that account's record. Showing the paper
    bot's own handful of bets there read as if the simulation had made them."""
    out = run(inputs=dry_inputs())[0]
    hero = out.by_id("hero")
    text = hero_text(out)
    assert "4005" in text.replace(",", "")          # the sim's wins
    assert "195" in text                             # the sim's losses: 4,200 bets less 4,005 won
    assert "95.4%" in text                           # its win rate, the replay's own
    assert "94.1%" in text                           # its break-even


@needs_node
def test_without_a_sim_the_scoreboard_is_still_the_paper_bots():
    """No backtest file yet: the hero is the paper ledger's, and so is its scoreboard."""
    g = dry_inputs()
    g["state"]["sim"] = None
    text = hero_text(run(inputs=g)[0])
    assert "4005" not in text.replace(",", "") and "Won" in text


def test_the_sim_carries_its_win_rate_and_break_even(home, lab):
    """The page cannot work these out from bets and wins: the break-even is the average cost of a contract."""
    write_study(lab)
    s = dashboard.sim()
    assert s["winRate"] == 0.9536 and s["need"] == 0.9412


def test_the_sim_says_when_each_asset_class_and_each_market_had_its_first_bet(home, lab):
    """Added Nov 8, 2026: the Tape page's long chart marks when metals and the other classes came in. The run's
    own byGroup and bySeries carry each one's first bet; the sim passes on just the name and that date, oldest first,
    and drops anything without a date (a class it never bet) or that isn't a row at all."""
    write_study(lab, run={**RUN,
        "byGroup": [{"key": "metals", "first": "2026-08-03T17:30:00+00:00", "n": 2195, "pnl": 264.82},
                    {"key": "crypto", "first": "2025-12-20T00:00:00+00:00", "n": 20657},
                    {"key": "fx", "first": None}, {"key": "energy"}, "not a row", {"first": "2026-01-01T00:00:00+00:00"}],
        "bySeries": [{"key": "GOLD", "first": "2026-08-03T20:30:00+00:00", "pnl": 167.37},
                     {"key": "BTC", "first": "2025-12-20T00:00:00+00:00"}, {"key": "ZEC", "first": ""}, None]})
    s = dashboard.sim()
    assert s["groups"] == [{"key": "crypto", "first": "2025-12-20T00:00:00+00:00"},
                           {"key": "metals", "first": "2026-08-03T17:30:00+00:00"}]
    assert s["markets"] == [{"key": "BTC", "first": "2025-12-20T00:00:00+00:00"},
                            {"key": "GOLD", "first": "2026-08-03T20:30:00+00:00"}]
