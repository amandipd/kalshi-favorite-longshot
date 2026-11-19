"""findings.py: the warning signs, selling early, halts and loss clusters behind findings.json.

The money helpers are checked by hand, each price-path shape on a path built to be it, and `main()` on the
synthetic history -- including the forward test, read from a paper.db the paper trader's own schema builds.
"""

from __future__ import annotations

import json
import math
import sqlite3

import pytest


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def bet(won=True, entry=0.96, t=0.0, group="crypto", bids=None, q8=(0.94, 0.96), **minutes):
    """A bet whose own (bid, ask) is q8 at every minute 1-14, or bid b with ask b + 0.02 where `bids` says."""
    q = {m: q8 for m in range(1, 15)}
    for m, b in (bids or {}).items():
        q[m] = None if b is None else (b, round(b + 0.02, 4))
    q.update({int(k[1:]): v for k, v in minutes.items()})
    return {"t": t, "series": "KXBTC15M", "group": group, "entry": entry, "won": won, "q": q}


# ------------------------------------------------------------------ money


def test_fav_quotes_flip_the_book_for_no(study):
    f = study.findings.fav_quotes
    assert f("yes", 0.94, 0.96) == (0.94, 0.96) and f("no", 0.03, 0.05) == (0.95, 0.97) and f("no", None, 0.5) is None


def test_held_and_sold_by_hand(study):
    fd = study.findings
    c = 10 / 0.96
    assert fd.held(bet(True)) == pytest.approx(c - 10 - fee(c, 0.96))
    assert fd.held(bet(False)) == pytest.approx(-10 - fee(c, 0.96))
    assert fd.sold(bet(False), 0.5) == pytest.approx(c * 0.5 - fee(c, 0.5) - 10 - fee(c, 0.96))
    assert fd.sold(bet(False), 0.0) == pytest.approx(-10 - fee(c, 0.96)), "nothing to pay a fee on at zero"
    assert fd.held(bet(True), c=3) == pytest.approx(3 - 3 * 0.96 - fee(3, 0.96))


def test_halves_and_summary(study):
    fd = study.findings
    bs = [bet(True, t=fd.SPLIT - 1), bet(False, t=fd.SPLIT), bet(True, t=fd.SPLIT + 1)]
    h = fd.halves(bs)
    assert len(h["before"]) == 1 and len(h["after"]) == 2
    s = fd.summary(h["after"])
    assert s["bets"] == 2 and s["lost"] == 0.5 and s["perBet"] == round(fd.total(h["after"]) / 2 * 100, 1)
    assert fd.summary([])["perBet"] is None and fd.cents(0.123) == 12.3


@pytest.mark.parametrize("sign,b,expected", [
    ("spread", bet(q8=(0.94, 0.96)), True),
    ("spread", bet(q8=(0.945, 0.96)), False),
    ("late", bet(bids={6: 0.48}), True),
    ("late", bet(bids={7: 0.83}, q8=(0.94, 0.96)), True),     # 84c -> 95c mid: up 11c
    ("late", bet(), False),
    ("slow", bet(bids={5: 0.6}), True),
    ("slow", bet(bids={5: None}), False),
])
def test_each_warning_sign(study, sign, b, expected):
    assert study.findings.SIGNS[sign][1](b) is expected


@pytest.mark.parametrize("bids,expected", [
    ([0.9, 0.9, 0.9, 0.85, 0.7, 0.3], "late crash"),
    ([0.75, 0.9, 0.9, 0.9, 0.9, 0.9], "early break"),
    ([0.85, 0.85, 0.65, 0.7, 0.92, 0.9], "whipsaw"),
    ([0.89, 0.88, 0.86, 0.75, 0.6, 0.55], "steady slide"),
    ([0.89, 0.95, 0.85, 0.75, 0.9, 0.6], "other"),
    ([0.9, None, 0.9, 0.9, 0.9, 0.9], None),
])
def test_each_price_path_shape(study, bids, expected):
    assert study.findings.shape(bet(bids=dict(zip(range(9, 15), bids)))) == expected


def test_first_bid_and_rule_delta(study):
    fd = study.findings
    b = bet(False, bids={9: 0.95, 10: 0.7, 11: 0.4})
    assert fd.first_bid(b, 0.8) == 0.7 and fd.first_bid(b, 0.8, start=11) == 0.4
    assert fd.first_bid(b, 0.9, above=True) == 0.95 and fd.first_bid(b, 0.1) is None
    assert fd.rule_delta([b], 0.8) == round(fd.sold(b, 0.7) - fd.held(b), 2)
    c = 10 / 0.96
    mid = (0.7 + 0.72) / 2
    assert fd.rule_delta([b], 0.8, at_mid=True) == round(c * mid - 10 - fee(c, 0.96) - fd.held(b), 2)
    assert fd.rule_delta([bet(True)], 0.5) == 0.0


def test_signs_report_every_combination_on_both_halves_and_forward(study):
    fd = study.findings
    bs = [bet(False, t=fd.SPLIT - 1, q8=(0.90, 0.96)), bet(True, t=fd.SPLIT, q8=(0.95, 0.96))]
    out = fd.signs(bs, [bet(True)])
    assert set(out["signs"]) == set(fd.SIGNS) and len(out["rows"]) == 5
    spread = out["rows"][0]
    assert spread["skip"] == ["spread"] and spread["before"]["skipped"] == 1.0 and spread["after"]["skipped"] == 0.0
    assert out["base"]["forward"]["bets"] == 1


def test_clusters_count_losses_per_window(study):
    fd = study.findings
    bs = [bet(False, t=1), bet(False, t=1), bet(False, t=1), bet(False, t=2), bet(True, t=3)]
    c = fd.clusters(bs)
    assert c["windows"] == {"1": 1, "3": 1} and c["shareIn3Plus"] == 0.75


# ------------------------------------------------------------------ the synthetic history


def test_load_takes_every_minute_8_favourite_in_the_edge_groups(study):
    fd = study.findings
    bets = fd.load()
    assert bets and all(0.90 + fd.SLIP - 1e-9 <= b["entry"] <= 0.999 for b in bets)
    assert {b["group"] for b in bets} <= {"crypto", "metals", "energy"}
    assert all(fd.FIRST <= b["t"] <= fd.LAST for b in bets)
    assert len({(b["t"], b["series"]) for b in bets}) == len(bets)


def test_forward_reads_a_paper_database_when_one_is_present(study, tmp_path, monkeypatch):
    """The paper trader is retired, so there is normally no paper.db and no forward days. One left in place, in
    the paper trader's schema, is still read: only the $10 account's settled bets that have a minute-8 bar."""
    fd = study.findings
    assert fd.forward() == []
    monkeypatch.chdir(tmp_path)          # forward() reads paper/paper.db from the working directory
    (tmp_path / "paper").mkdir()
    db = sqlite3.connect(tmp_path / "paper" / "paper.db")
    try:
        db.executescript("""
            CREATE TABLE minute_bars (ticker TEXT, series TEXT, minute INTEGER, ts REAL, yes_bid REAL, yes_ask REAL);
            CREATE TABLE bets (strategy TEXT, ticker TEXT, series TEXT, window_open REAL, side TEXT, fill REAL,
                               status TEXT);""")
        db.executemany("INSERT INTO minute_bars VALUES (?,?,?,?,?,?)",
                       [("T1", "KXBTC15M", m, 0, 0.94, 0.96) for m in range(1, 15)] + [("T2", "KXBTC15M", 7, 0, 0.1, 0.2)])
        db.executemany("INSERT INTO bets VALUES (?,?,?,?,?,?,?)",
                       [("m8", "T1", "KXBTC15M", 100.0, "no", 0.95, "won"),    # has minute 8: kept
                        ("m8", "T2", "KXBTC15M", 200.0, "yes", 0.95, "lost"),  # no minute-8 bar: dropped
                        ("m8", "T3", "KXBTC15M", 300.0, "yes", 0.95, "open"),  # unsettled: dropped
                        ("m8c", "T1", "KXBTC15M", 100.0, "no", 0.95, "won")])  # another account: ignored
        db.commit()
    finally:
        db.close()
    fwd = fd.forward()
    assert len(fwd) == 1 and fwd[0]["won"] is True and fwd[0]["entry"] == 0.95
    assert fwd[0]["q"][8] == (0.04, 0.06) and fwd[0]["q"][1] == (0.04, 0.06)


@pytest.fixture(scope="module")
def findings(study):
    study.findings.main()
    with open("findings.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_main_writes_every_section(study, findings):
    assert (findings["from"], findings["jul18"], findings["split"], findings["to"]) == ("2025-12-10", "2026-07-18", "2026-08-24",
                                                                                     "2026-10-01")
    for key in ("periods", "forwardBets", "halts", "exits", "signs", "clusters"):
        assert key in findings
    bets = study.findings.load()
    assert sum(findings["periods"][k]["bets"] for k in ("pre", "before", "after")) == len(bets)
    assert findings["periods"]["pre"]["bets"] == sum(b["t"] < study.findings.JUL18 for b in bets) > 0


def test_selling_early_bookkeeping_adds_up(findings):
    exits = findings["exits"]
    for row in exits["under50"]:
        assert row["net"] == pytest.approx(row["rescued"] - row["thrown"], abs=0.011)
    assert [r["under"] for r in exits["stops"]] == [0.90, 0.80, 0.50, 0.30, 0.10]
    assert [r["minute"] for r in exits["byMinute"]] == list(range(9, 15))
    assert sum(s["losers"] for s in exits["shapes"]) <= exits["losers"]
    for b in exits["bounce"]:
        assert 0 <= b["fellFurther"] <= 1 and 0 <= b["won"] <= 1


def test_every_halt_rule_is_run_from_both_starts(findings):
    rows = {r["rule"]: r for r in findings["halts"]}
    assert len(rows) == 6 and "Today's halts" in rows and "No halts" in rows
    for r in rows.values():
        for key in ("fromDec10", "fromJul18", "fromAug24"):
            assert (r[key]["stopped"] is None) == (r[key]["why"] is None)
    assert rows["No halts"]["fromJul18"]["why"] in (None, "broke")


def test_main_counts_the_forward_bets(study, findings):
    assert findings["forwardBets"] == len(study.findings.forward())

