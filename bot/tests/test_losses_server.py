"""The server side of the Edge view's live-loss panels: what the research writes about how the
live bot's losses happened, and the skip rule they suggested backtested (live_losses.json), reaches the study as
study()["losses"], and running the research again moves the study's stamp so the page fetches it again.

How these tests read the requirements:
  - "passes the JSON through" is equality with what the file holds, en dashes and cents signs included: the server
    adds, drops and reshapes nothing (as study()["floor"] does with price_floor.json).
  - "missing or broken" is a missing file, an empty file, text that isn't JSON and JSON cut off part way: each reads
    as None, and the rest of the study is still served.
  - study()'s docstring names live_losses.json, as it names every other file.
  - The study route (/api/research) carries the losses too, read again once the file is written again, as the
    price-floor test's route test does.

    python -m pytest tests/test_losses_server.py -q
"""
import json

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import fetch, lab, serving, write  # noqa: F401 (lab is a fixture pytest finds by name)

S = {"bets": 3750, "perBet": 7.1, "mu": 7.4, "lo": 1.2, "hi": 13.6, "pnl": 2775.0, "lost": 0.0784, "implied": 0.0907}
EMPTY = {"bets": 0, "perBet": None, "mu": None, "lo": None, "hi": None, "pnl": None, "lost": None, "implied": None}
LOSSES = {
    "asOf": 1791870000.0,
    "live": {"from": 1790611200.0, "to": 1791832500.0, "bets": 613, "lost": 25, "pnl": 194.08, "staked": 9394.12,
             "bands": [{"key": "90-92", "label": "90–92¢", "bets": 130, "lost": 16, "pnl": -61.37, "staked": 2010.5,
                        "implied": 0.0912, "backtest": 0.0745},
                       {"key": "94+", "label": "94¢ and up", "bets": 0, "lost": 0, "pnl": 0.0, "staked": 0.0,
                        "implied": None, "backtest": None}],
             "wide": {"bets": 41, "lost": 7, "pnl": -48.6, "staked": 640.0},
             "rest": {"bets": 572, "lost": 18, "pnl": 242.68, "staked": 8754.12},
             "watch": {"bets": 130, "lost": 16, "expected": 9.69, "p": 0.039},
             "flips": {str(k): k - 9 for k in range(9, 16)}, "flipsOf": 25,
             "clusters": {"cryptoLost": 21, "inMulti": 10},
             "days": [{"day": "2026-09-28", "bets": 38, "lost": 4, "pnl": -2.15, "staked": 76.4, "stake": 2.01}]},
    "rule": {"lo": 0.90, "hi": 0.92, "spread": 0.002, "slip": 0.004, "start": 500.0, "from": 1765342800, "to": 1791518400,
             "periods": [{"key": "pre", "label": "Dec 10 – Jul 17"}, {"key": "post", "label": "Jul 18 – Oct 8"},
                         {"key": "all", "label": "Dec 10 – Oct 8"}],
             "rows": {k: {"pre": S, "post": EMPTY, "all": S} for k in ("skipped", "kept", "band", "live")},
             "family": [{"hi": 0.91, "spread": None, "pre": S, "post": S}],
             "holdout": [{"chosenOn": "pre", "scoredOn": "post", "hi": 0.93, "spread": None, "chosen": S, "scored": S}],
             "holds": False,
             "sizing": {"live": {"all": {"start": 500.0, "final": 25132.4, "bets": 41230, "maxDD": 0.41, "broke": None}},
                        "skip": {"all": {"start": 500.0, "final": 0.0, "bets": 900, "maxDD": 1.0, "broke": "2026-03-04"}}}},
}


# ------------------------------------------------------------------ the research files
def test_the_live_losses_file_is_one_of_the_research_files():
    assert "live_losses.json" in dashboard.STUDY_FILES


def test_the_files_it_had_are_all_still_there():
    for name in ("strategies.json", "findings.json", "key_stats.json", "all_markets.json", "sizing.json", "price_floor.json"):
        assert name in dashboard.STUDY_FILES, name
    assert len(dashboard.STUDY_FILES) == len(set(dashboard.STUDY_FILES)), "no file is listed twice"


def test_the_stamp_moves_when_the_live_losses_research_is_run_again(lab):
    write(lab, "findings.json", {}, mtime=1000)
    write(lab, "price_floor.json", {}, mtime=2000)
    write(lab, "live_losses.json", LOSSES, mtime=4000)
    assert dashboard.stamp() == 4000
    write(lab, "live_losses.json", LOSSES, mtime=5000)
    assert dashboard.stamp() == 5000


def test_the_live_losses_file_alone_sets_the_stamp(lab):
    write(lab, "live_losses.json", LOSSES, mtime=3000)
    assert dashboard.stamp() == 3000


# ------------------------------------------------------------------ study()["losses"]
def test_the_study_passes_the_live_losses_through(lab):
    write(lab, "live_losses.json", LOSSES)
    assert dashboard.study()["losses"] == LOSSES


def test_the_live_losses_sit_beside_the_rest_of_the_study(lab):
    write(lab, "price_floor.json", {"rule": {"lo": 0.9}})
    write(lab, "live_losses.json", LOSSES)
    s = dashboard.study()
    assert s["losses"] == LOSSES and s["floor"] == {"rule": {"lo": 0.9}}, "each file in its own field"


def test_no_live_losses_until_the_research_is_run(lab):
    s = dashboard.study()
    assert "losses" in s and s["losses"] is None


@pytest.mark.parametrize("broken", ["{not json", "", '{"live": {"bets": 613', "\x00\x01"],
                         ids=["not json", "empty", "cut off", "binary"])
def test_a_broken_live_losses_file_reads_as_none(lab, broken):
    write(lab, "live_losses.json", broken)
    write(lab, "price_floor.json", {"rule": {"lo": 0.9}})
    s = dashboard.study()
    assert s["losses"] is None
    assert s["floor"] == {"rule": {"lo": 0.9}}, "the rest of the study is still read"


def test_the_study_docstring_names_the_live_losses_file():
    assert "live_losses.json" in (dashboard.study.__doc__ or "")


# ------------------------------------------------------------------ the route
def test_the_study_route_carries_the_live_losses_and_reads_them_again_when_they_change(lab):
    write(lab, "live_losses.json", LOSSES, mtime=1000)
    with serving() as base:
        status, _, body = fetch(base, "/api/research")
        newer_losses = {**LOSSES, "rule": {**LOSSES["rule"], "holds": True}}
        write(lab, "live_losses.json", newer_losses, mtime=2000)   # the research run again: read again
        newer = json.loads(fetch(base, "/api/research")[2])
        stamp = json.loads(fetch(base, "/api/research/stamp")[2])
    assert status == 200 and json.loads(body)["losses"] == LOSSES
    assert newer["losses"]["rule"]["holds"] is True and newer["stamp"] == 2000
    assert stamp["stamp"] == 2000


def test_the_study_route_says_null_without_the_file(lab):
    with serving() as base:
        status, _, body = fetch(base, "/api/research")
    assert status == 200 and json.loads(body)["losses"] is None
