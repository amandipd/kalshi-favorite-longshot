"""The server side of the Research tab's price-floor panel: the price-floor test the research writes (price_floor.json)
reaches the study, and the live bets come split by the price paid, in the same bands, to set beside it.

    python -m pytest tests/test_price_floor_server.py -q
"""
import json

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import NOW, add_bet, fetch, home, lab, mode_db, serving, write  # noqa: F401 (fixtures pytest finds by name)

FLOOR = {"bands": [{"key": "90-91", "bets": 120, "perBet": -0.4}], "rule": {"lo": 0.90, "hi": 0.95}}


# ------------------------------------------------------------------ the study: price_floor.json
def test_the_price_floor_test_is_one_of_the_research_files():
    assert "price_floor.json" in dashboard.STUDY_FILES


def test_the_stamp_moves_when_the_price_floor_test_is_run_again(lab):
    write(lab, "findings.json", {}, mtime=1000)
    write(lab, "price_floor.json", FLOOR, mtime=4000)
    assert dashboard.stamp() == 4000
    write(lab, "price_floor.json", FLOOR, mtime=5000)
    assert dashboard.stamp() == 5000


def test_the_study_carries_the_price_floor_test(lab):
    write(lab, "price_floor.json", FLOOR)
    assert dashboard.study()["floor"] == FLOOR


def test_no_price_floor_test_until_it_is_run(lab):
    assert dashboard.study()["floor"] is None


def test_a_broken_price_floor_file_reads_as_none(lab):
    write(lab, "price_floor.json", "{not json")
    assert dashboard.study()["floor"] is None


def test_the_study_route_carries_the_price_floor_test(lab):
    write(lab, "price_floor.json", FLOOR, mtime=1000)
    with serving() as base:
        status, _, body = fetch(base, "/api/research")
        write(lab, "price_floor.json", {**FLOOR, "rule": {"lo": 0.92}}, mtime=2000)   # run again: read again
        newer = json.loads(fetch(base, "/api/research")[2])
    assert status == 200 and json.loads(body)["floor"] == FLOOR
    assert newer["floor"]["rule"] == {"lo": 0.92} and newer["stamp"] == 2000


# ------------------------------------------------------------------ the live bets by the price paid
def test_the_bands_match_the_research():
    assert dashboard.PRICE_BANDS == ((90, 91), (92, 94), (95, 97), (98, 99))


def test_settled_bets_by_the_price_paid_low_to_high(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", price=0.9075, contracts=4, status="won", pnl=0.30)   # 90.75c: 90c
    add_bet(db, "KXBTC15M-2", price=0.91, contracts=2, status="lost", pnl=-1.83)
    add_bet(db, "KXBTC15M-3", price=0.9199999999, contracts=5, status="won", pnl=0.35)   # 92c, stored a hair under
    add_bet(db, "KXETH15M-1", price=0.80, contracts=1, status="lost", pnl=-0.81)   # filled below the order's 90c
    add_bet(db, "KXETH15M-2", price=0.999, contracts=10, status="won", pnl=0.0)     # 99.9c: still 98-99
    add_bet(db, "KXETH15M-3", price=0.96, contracts=3, status="open")               # open: not yet counted
    add_bet(db, "KXSOL15M-1", price=1.0, contracts=1, status="lost", pnl=-1.0)      # past every band (shouldn't happen): left out
    rows = dashboard.state("live-prod")["byPrice"]
    assert [(r["key"], r["label"]) for r in rows] == [("under-90", "under 90¢"), ("90-91", "90–91¢"), ("92-94", "92–94¢"),
                                                      ("98-99", "98–99¢")]   # 95-97 holds only the open bet: not listed
    by = {r["key"]: r for r in rows}
    assert (by["90-91"]["n"], by["90-91"]["wins"]) == (2, 1)
    assert by["90-91"]["pnl"] == pytest.approx(0.30 - 1.83) and by["90-91"]["staked"] == pytest.approx(4 * 0.9075 + 2 * 0.91)
    assert (by["92-94"]["n"], by["92-94"]["wins"], by["92-94"]["staked"]) == (1, 1, pytest.approx(4.6))
    assert by["92-94"]["pnl"] == pytest.approx(0.35)
    assert (by["under-90"]["n"], by["under-90"]["wins"], by["under-90"]["pnl"]) == (1, 0, pytest.approx(-0.81))
    assert by["under-90"]["staked"] == pytest.approx(0.80)                     # the cost, not cost and fee, as bySeries
    assert (by["98-99"]["n"], by["98-99"]["wins"], by["98-99"]["staked"]) == (1, 1, pytest.approx(9.99))
    assert set(by["90-91"]) == {"key", "label", "n", "wins", "pnl", "staked"}


def test_the_bands_follow_the_price_not_the_order_they_settled_in(home):
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", price=0.98, settled=NOW - 100)
    add_bet(db, "KXBTC15M-2", price=0.95, settled=NOW - 200)
    add_bet(db, "KXBTC15M-3", price=0.89, settled=NOW - 300)
    assert [r["key"] for r in dashboard.state("live-prod")["byPrice"]] == ["under-90", "95-97", "98-99"]


def test_each_band_edge_is_in_its_band(home):
    db = mode_db(home, "live-prod")
    for i, price in enumerate((0.8999, 0.90, 0.91, 0.92, 0.94, 0.95, 0.97, 0.98, 0.99)):
        add_bet(db, f"KXBTC15M-{i}", price=price)
    assert [(r["key"], r["n"]) for r in dashboard.state("live-prod")["byPrice"]] == [
        ("under-90", 1), ("90-91", 2), ("92-94", 2), ("95-97", 2), ("98-99", 2)]


def test_no_bets_no_bands(home):
    mode_db(home, "dry-demo")
    assert dashboard.state("dry-demo")["byPrice"] == []
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", price=0.93, status="open")                     # an open bet alone: nothing settled yet
    assert dashboard.state("live-prod")["byPrice"] == []


def test_a_bet_is_banded_by_the_ask_it_saw_as_the_backtest_is(home):
    """The backtest bands each bet by the ask at minute 8; a live order often fills below the ask it saw (the book moved
    its way), so the live bets are banded by the decision's price when there is one, and by the price paid otherwise."""
    db = mode_db(home, "live-prod")
    add_bet(db, "KXBTC15M-1", price=0.917, status="won", pnl=0.40)    # saw 92c, paid 91.7c: 92-94, like the backtest
    add_bet(db, "KXETH15M-1", price=0.947, status="won", pnl=0.20)    # saw 95.7c, paid 94.7c: 95-97
    add_bet(db, "KXSOL15M-1", price=0.91, status="lost", pnl=-1.8)    # a decision with no price: what it paid
    add_bet(db, "KXDOGE15M-1", price=0.93, status="won", pnl=0.30)    # no decision row (an older ledger): what it paid
    for ticker, seen in (("KXBTC15M-1", 0.92), ("KXETH15M-1", 0.957), ("KXSOL15M-1", None), ("KXXRP15M-1", 0.90)):   # XRP: no bet
        db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,?,?)",
                   (NOW - 4000, ticker, ticker.split("-")[0], "yes", seen, "bet", "bought"))
    db.commit()
    by = {r["key"]: r for r in dashboard.state("live-prod")["byPrice"]}
    assert set(by) == {"90-91", "92-94", "95-97"}
    assert (by["90-91"]["n"], by["90-91"]["wins"]) == (1, 0) and by["92-94"]["pnl"] == pytest.approx(0.40 + 0.30)
    assert by["95-97"]["n"] == 1 and by["92-94"]["staked"] == pytest.approx(3 * 0.917 + 3 * 0.93)   # still what it paid
