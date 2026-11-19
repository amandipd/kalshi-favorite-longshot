"""key_stats.py's book depth and real fills: the edges book_depth() meets, and main() with a trade tape beside it.

book_depth() turns liquidity.json's `seen` (contracts others bought at the bot's price or better in the seconds after
its order) into dollars at DEPTH_PRICE, so every test counts whole contracts the way the tape does. main() is run once
in a copy of the synthetic history with a liquidity.json and a real-liquidity account, the case the synthetic history
alone never reaches.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest


@pytest.fixture
def ks(study):
    import key_stats
    return key_stats


def tape(seen, depth=30):
    """liquidity.json with one market per (ticker, contracts seen)."""
    return {"send": 482, "depth": depth, "markets": {t: [None, None, float(v)] for t, v in seen.items()}}


def test_markets_that_tie_on_the_50_dollar_share_are_listed_by_series(ks):
    d = ks.book_depth(tape({"KXZEC15M-A": 60, "KXBTC15M-A": 60, "KXETH15M-A": 0, "KXSOL15M-A": 60, "KXSOL15M-B": 0}),
                      {"KXZEC15M": "crypto", "KXBTC15M": "crypto", "KXETH15M": "crypto", "KXSOL15M": "crypto"})
    assert [(m["series"], m["atLeast"]["50"]) for m in d["markets"]] == [
        ("KXBTC15M", 1.0), ("KXZEC15M", 1.0), ("KXSOL15M", 0.5), ("KXETH15M", 0.0)]   # deepest first, ties by name


def test_a_series_the_catalog_doesnt_know_counts_as_other(ks):
    d = ks.book_depth(tape({"KXNEW15M-A": 30, "KXBTC15M-A": 30}), {"KXBTC15M": "crypto"})
    assert set(d["groups"]) == {"crypto", "other"} and d["groups"]["other"]["orders"] == 1
    assert {m["series"]: m["group"] for m in d["markets"]} == {"KXNEW15M": "other", "KXBTC15M": "crypto"}


@pytest.mark.parametrize("dollars", [10, 25, 50, 100])
def test_each_dollar_level_counts_an_order_that_saw_exactly_that_much(ks, dollars):
    exactly = dollars / ks.DEPTH_PRICE                      # contracts worth exactly $X at the bot's price
    d = ks.book_depth({"depth": 30, "markets": {"KXBTC15M-A": [None, None, exactly],
                                                "KXBTC15M-B": [None, None, exactly - 0.01]}}, {"KXBTC15M": "crypto"})
    assert d["all"]["atLeast"][str(dollars)] == 0.5         # exactly $X counts; a cent's worth less doesn't


@pytest.mark.parametrize("contracts, levels", [(10, []), (11, ["10"]), (27, ["10", "25"]), (53, ["10", "25", "50"]),
                                              (105, ["10", "25", "50"]), (106, ["10", "25", "50", "100"])])
def test_whole_contracts_reach_each_level_at_95_cents(ks, contracts, levels):
    d = ks.book_depth(tape({"KXBTC15M-A": contracts}), {"KXBTC15M": "crypto"})
    assert [k for k, share in d["all"]["atLeast"].items() if share == 1.0] == levels


def test_a_tape_where_nothing_ever_traded(ks):
    d = ks.book_depth(tape({"KXBTC15M-A": 0, "KXBTC15M-B": 0, "KXGOLD15M-A": 0}), {"KXBTC15M": "crypto", "KXGOLD15M": "metals"})
    for s in [d["all"], *d["groups"].values(), *d["markets"]]:
        assert s["none"] == 1.0 and s["median"] == 0.0 and set(s["atLeast"].values()) == {0.0}
    assert [m["series"] for m in d["markets"]] == ["KXBTC15M", "KXGOLD15M"]          # all tied: by name


def test_the_median_is_in_dollars_and_takes_the_upper_middle_of_an_even_count(ks):
    d = ks.book_depth(tape({"KXBTC15M-A": 0, "KXBTC15M-B": 10, "KXBTC15M-C": 20, "KXBTC15M-D": 40}), {"KXBTC15M": "crypto"})
    assert d["all"]["median"] == pytest.approx(20 * ks.DEPTH_PRICE)
    assert d["depth"] == 30 and list(d["groups"]) == ["crypto"]


def test_groups_are_listed_by_name(ks):
    d = ks.book_depth(tape({"KXWTI15M-A": 1, "KXBTC15M-A": 1, "KXGOLD15M-A": 1}),
                      {"KXWTI15M": "energy", "KXBTC15M": "crypto", "KXGOLD15M": "metals"})
    assert list(d["groups"]) == ["crypto", "energy", "metals"]


def test_read_json_is_none_for_a_missing_file(ks, tmp_path):
    assert ks.read_json(str(tmp_path / "liquidity.json")) is None
    (tmp_path / "x.json").write_text('{"a": 1}', encoding="utf-8")
    assert ks.read_json(str(tmp_path / "x.json")) == {"a": 1}


def test_main_reports_real_fills_and_book_depth_when_the_tape_is_there(study, ks, tmp_path, monkeypatch, capsys):
    study.history.write_snapshots()
    for name, module in (("findings.json", study.findings), ("strategies.json", study.strategies_backtest)):
        if not os.path.exists(name):
            module.main()
    for name in ("universe.json", "minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv", "minutes_pre.csv",
                 "snapshots_all.csv", "findings.json", "strategies.json"):
        shutil.copy(study.dir / name, tmp_path / name)
    s = json.loads((tmp_path / "strategies.json").read_text(encoding="utf-8"))
    for start in s["starts"].values():                 # a real-liquidity account beside the live bot, from every start
        live = start["backtest"]["live"]
        start["backtest"]["liveliq"] = {**live, "final": live["start"] + 1, "bets": max(1, live["bets"] // 2),
                                        "liquidity": {"asked": 200.0, "got": 104.0, "orders": 20, "missed": 8, "missedWon": 8,
                                                      "partial": 3}}
    s["starts"]["aug24"]["backtest"]["liveliq"]["liquidity"] = {"asked": 0.0, "got": 0.0, "orders": 0, "missed": 0, "missedWon": 0,
                                                              "partial": 0}   # no orders from this start: no line for it
    (tmp_path / "strategies.json").write_text(json.dumps(s), encoding="utf-8")
    (tmp_path / "liquidity.json").write_text(json.dumps(tape({"KXBTC15M-A": 60, "KXGOLD15M-A": 0})), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    ks.main()
    out = capsys.readouterr().out
    k = json.loads((tmp_path / "key_stats.json").read_text(encoding="utf-8"))
    assert list(k["realFills"]) == list(s["starts"]) and k["realFills"]["jul18"]["got"] == 104.0
    assert k["bookDepth"]["all"]["orders"] == 2 and set(k["bookDepth"]["groups"]) == {"crypto", "metals"}
    assert out.count("real fills from ") == len(s["starts"]) - 1 and "real fills from aug24" not in out
    assert "52% of contracts, 8 of 20 orders got nothing" in out and k["realFills"]["aug24"]["orders"] == 0
    assert "book depth: median $57 at the bot's price within 30 s; $50 or more in 50% of orders, nothing in 50%" in out
