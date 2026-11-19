"""stress_signals.py (warning signs at minute 8), all_markets.py (every market group) and key_stats.py (the
numbers the findings dashboard quotes).

The synthetic history's windows sit on known clock slots -- 12:30, 13:30, 14:00 and 18:00 UTC are 8:30, 9:30,
10:00 am and 2:00 pm in New York in summer -- so the clock flags can be checked exactly.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

UTC = timezone.utc


def t(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


# ------------------------------------------------------------------ stress_signals


@pytest.fixture(scope="module")
def windows(study):
    return study.stress_signals.load()


def test_load_keeps_every_market_and_marks_the_bets(study, windows):
    ss = study.stress_signals
    assert sum(len(ms) for ms in windows.values()) == len(study.data["rows"])
    bets = [m["bet"] for ms in windows.values() for m in ms if "bet" in m]
    assert bets
    for b in bets:
        assert 0.90 <= b["price"] - ss.SLIP + 1e-9 and b["price"] <= 0.999
        assert b["pnl"] == pytest.approx((ss.sb.STAKE / b["price"] if b["won"] else 0) - ss.sb.STAKE
                                         - ss.fee(ss.sb.STAKE / b["price"], b["price"]))
        assert b["low"] <= 1 and b["chop"] >= -1e-9


@pytest.mark.parametrize("when,flags", [
    ("2026-07-20T12:30:00Z", {"news": True, "open": False, "fed": False, "weekend": False}),   # Mon 8:30 ET
    ("2026-07-20T13:30:00Z", {"news": False, "open": True, "fed": False, "weekend": False}),   # Mon 9:30 ET
    ("2026-07-20T14:00:00Z", {"news": True, "open": False, "fed": False}),                     # Mon 10:00 ET
    ("2026-07-29T18:00:00Z", {"news": True, "fed": True}),                                     # Fed day, 2:00 ET
    ("2026-07-30T18:00:00Z", {"news": True, "fed": False}),
    ("2026-07-18T12:30:00Z", {"news": False, "weekend": True}),                               # Saturday
    ("2026-01-12T13:30:00Z", {"news": True, "open": False, "weekend": False}),                # Mon 8:30 EST, winter time
    ("2026-01-12T14:00:00Z", {"news": False, "open": False}),                                 # Mon 9:00 EST
])
def test_the_clock_flags(study, windows, when, flags):
    w = study.stress_signals.window_features(windows)[t(when)]
    for key, value in flags.items():
        assert w[key] is value, key


def test_window_features_count_bets_and_carry_losses_forward(study, windows):
    feats = study.stress_signals.window_features(windows)
    order = sorted(windows)
    losses = [sum(not m["bet"]["won"] for m in windows[w] if "bet" in m) for w in order]
    for i, w in enumerate(order[:200]):
        assert feats[w]["nbets"] == sum("bet" in m for m in windows[w])
        assert feats[w]["prev_losses"] == (losses[i - 1] if i else 0)
        assert feats[w]["day_losses"] == sum(losses[max(0, i - 96):i])


def test_stats_clusters_by_window(study):
    stats = study.stress_signals.stats
    assert stats([]) is None
    rows = [(1, {"pnl": 0.5, "won": True, "price": 0.95}), (1, {"pnl": -10.0, "won": False, "price": 0.95}),
            (2, {"pnl": 0.5, "won": True, "price": 0.96})]
    s = stats(rows)
    assert s["n"] == 3 and s["win"] == pytest.approx(2 / 3) and s["mu"] == pytest.approx(-9 / 3 * 100)
    assert s["lo"] < s["mu"] < s["hi"]
    assert stats(rows[:1])["lo"] is None


def test_fmt_split_and_tables(study, capsys):
    ss = study.stress_signals
    assert ss.fmt(None).strip() == "-"
    rows = [(ss.SPLIT - 1, {"pnl": 0.5, "won": True, "price": 0.95}), (ss.SPLIT, {"pnl": -10.0, "won": False, "price": 0.95})]
    pre, before, after = ss.split(rows)
    assert pre.strip() == "-" and "100.0%" in before and "0.0%" in after
    pre, _, _ = ss.split(rows + [(ss.JUL18 - 1, {"pnl": 0.4, "won": True, "price": 0.96})])
    assert "100.0%" in pre and ss.part(ss.JUL18 - 1) == 0 and ss.part(ss.JUL18) == 1 and ss.part(ss.SPLIT) == 2
    ss.by_fifths(rows, lambda t, b: b["pnl"], "pnl")
    ss.by_fifths([], lambda t, b: 1.0, "nothing")
    ss.by_flag(rows, lambda t, b: b["won"], "won")
    out = capsys.readouterr().out
    assert "pnl" in out and "nothing" not in out and "won" in out


def test_stress_signals_main(study, capsys):
    study.stress_signals.main()
    out = capsys.readouterr().out
    for heading in ("THE MARKET ITSELF", "THE WINDOW", "THE CLOCK", "RECENT RESULTS", "SKIPPING WINDOWS",
                    "THE 12 WORST WINDOWS", "the 8 worst"):
        assert heading in out


# ------------------------------------------------------------------ all_markets


def bet(t, group, won, ask=0.95, pnl=None):
    return {"t": t, "series": "S", "group": group, "ask": ask, "won": won,
            "pnl": pnl if pnl is not None else (0.5 if won else -10.0), "need": 0.95}


def test_bets_for_tags_each_bet_with_its_group(study):
    am = study.all_markets
    fav = {8: [("2026-07-18T00:00:00Z", "KXBTC15M", 0.95, True), ("2026-07-18T00:00:00Z", "KXGOLD15M", 0.92, False),
               ("2026-07-18T00:00:00Z", "KXCRYPTOLEAD15M", 0.96, True), ("2026-07-18T00:00:00Z", "KXBTC15M", 0.5, True)]}
    bs = am.bets_for(fav, 8)
    assert [b["group"] for b in bs] == ["crypto", "metals", "coin race"]
    price = 0.95 + am.SLIP
    assert bs[0]["pnl"] == pytest.approx(10 / price - 10 - study.minutes.fee(10 / price, price, "KXBTC15M", 1.0))


def test_group_caps_keep_the_highest_priced_favourite(study):
    am = study.all_markets
    bs = [bet("2026-07-18T00:00:00Z", "crypto", False, 0.93), bet("2026-07-18T00:00:00Z", "crypto", True, 0.97),
          bet("2026-07-18T00:00:00Z", "metals", True, 0.95), bet("2026-07-18T00:15:00Z", "crypto", True, 0.95)]
    uncapped = am.rule(bs, set())
    capped = am.rule(bs, {"crypto"})
    assert uncapped["n"] == 4 and capped["n"] == 3
    assert capped["total"] == pytest.approx(0.5 * 3)
    merged = am.rule(bs + [bet("2026-07-18T00:00:00Z", "coin race", False, 0.99)], set(), {"crypto", "coin race"})
    assert merged["n"] == 3, "crypto and Coin Race counted as one group: only the 99c Coin Race bet is kept"


def test_co_losses_need_20_pairs(study):
    am = study.all_markets
    bs = [b for i in range(25) for b in (bet(f"w{i:02d}", "crypto", False), bet(f"w{i:02d}", "metals", i % 2 == 0))]
    out = am.co_losses(bs)
    assert out["crypto|metals"]["n"] == 25 and out["crypto|metals"]["p"] == pytest.approx(12 / 25)
    assert "crypto|crypto" not in out


@pytest.fixture(scope="module")
def all_markets(study):
    study.all_markets.main()
    with open("all_markets.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_all_markets_main_covers_every_group_it_saw(study, all_markets):
    assert {"crypto", "metals", "energy", "fx", "coin race"} <= set(all_markets["groups"])
    assert set(all_markets["rules"]) == {"all", "orig16", "max1crypto", "max1group", "max1cryptodriven",
                                         "elig_max1crypto", "elig_max1group"}
    assert all_markets["rules"]["max1crypto"]["n"] <= all_markets["rules"]["all"]["n"]
    for g, s in all_markets["spreads"].items():
        assert 0 <= s["wide"] <= 1 and s["spread"] > 0, g
    assert all_markets["coinRaceUnderdog"], "the synthetic Coin Race has underdogs to buy"


# ------------------------------------------------------------------ key_stats


def test_kelly_table_has_one_row_per_fill_scenario(study):
    rows = study.key_stats.kelly_table(study.sizing.days_of_windows())
    assert [r["scenario"] for r in rows] == list(study.sizing.SCENARIOS)
    assert rows[0]["cost"] < rows[1]["cost"] <= rows[2]["cost"]
    assert rows[0]["kelly"] > rows[1]["kelly"] >= rows[2]["kelly"]


def test_exit_rules_pair_each_sell_account_with_its_base():
    import key_stats
    strategies = {"strategies": [{"id": "m8", "name": "$10"}, {"id": "m8x", "name": "$10 sell", "base": "m8"}],
                  "starts": {"aug24": {"backtest": {
                      "m8": {"final": 250.0, "broke": None},
                      "m8x": {"start": 240.0, "final": 230.0, "broke": None, "exit": {"sold": 3}}}}}}
    assert key_stats.exit_rules(strategies) == [{"name": "$10 sell", "base": "$10", "start": 240.0, "final": 230.0,
                                                 "broke": None, "baseFinal": 250.0, "baseBroke": None,
                                                 "exit": {"sold": 3}}]


def run_of(final, bets, win_rate, need, **more):
    return {"start": 225.0, "final": final, "broke": None, "bets": bets, "winRate": win_rate, "need": need,
            "perBet": 5.0, "maxDD": 0.3, "curve": [225.0], **more}


def test_real_fills_set_the_live_bot_filled_in_full_against_the_book_at_the_recorded_ask():
    import key_stats
    liq = {"asked": 100.0, "got": 52.0, "orders": 10, "missed": 4, "missedWon": 4, "partial": 1}
    strategies = {"starts": {
        "jul18": {"backtest": {"live": run_of(500.0, 10, 0.96, 0.94), "liveliq": run_of(300.0, 6, 0.95, 0.94, liquidity=liq)},
                  "live": {"live": run_of(400.0, 10, 0.96, 0.944), "liveliq": run_of(1.0, 6, 0.5, 0.94, liquidity=liq)}},
        "aug24": {"backtest": {"live": run_of(450.0, 8, 0.96, 0.94)}}}}   # no real-liquidity account from Aug 24
    out = key_stats.real_fills(strategies)
    assert list(out) == ["jul18"]                                             # only starts with both accounts
    q = out["jul18"]
    assert {k: q[k] for k in liq} == liq
    assert (q["full"]["final"], q["real"]["final"]) == (500.0, 300.0)        # the recorded-ask ("backtest") runs, not live-like
    assert q["full"]["kelly"] == pytest.approx((0.96 - 0.94) / (1 - 0.94))
    assert q["real"]["kelly"] == pytest.approx((0.95 - 0.94) / (1 - 0.94))
    assert set(q["full"]) == {"start", "final", "broke", "bets", "winRate", "need", "perBet", "maxDD", "kelly"}   # no curve


def test_real_fills_are_none_without_a_real_liquidity_account():
    import key_stats
    assert key_stats.real_fills({"starts": {"jul18": {"backtest": {"live": run_of(500.0, 10, 0.96, 0.94)}}}}) is None
    assert key_stats.real_fills({}) is None
    no_bets = {"starts": {"jul18": {"backtest": {"live": run_of(500.0, 10, 0.96, 0.94),
                                                 "liveliq": run_of(225.0, 0, None, None, liquidity={"asked": 0.0})}}}}
    assert key_stats.real_fills(no_bets)["jul18"]["real"]["kelly"] is None   # never filled: no Kelly to state


def test_book_depth_is_what_traded_at_the_bots_price_per_group_and_market():
    import key_stats
    liq = {"depth": 30, "markets": {"KXBTC15M-A": [1.0, 0.95, 200.0], "KXBTC15M-B": [None, None, 0.0],
                                    "KXGOLD15M-A": [2.0, 0.96, 20.0]}}
    d = key_stats.book_depth(liq, {"KXBTC15M": "crypto", "KXGOLD15M": "metals"})
    assert (d["depth"], d["price"], d["dollars"]) == (30, key_stats.DEPTH_PRICE, [10, 25, 50, 100])
    assert d["all"]["orders"] == 3 and d["all"]["none"] == pytest.approx(1 / 3)
    assert d["all"]["median"] == pytest.approx(20.0 * key_stats.DEPTH_PRICE)            # in dollars
    assert d["groups"]["metals"]["atLeast"] == {"10": 1.0, "25": 0.0, "50": 0.0, "100": 0.0}   # 20 contracts: about $19
    btc = d["markets"][0]
    assert (btc["series"], btc["group"], btc["orders"]) == ("KXBTC15M", "crypto", 2)        # deepest first
    assert btc["atLeast"]["100"] == pytest.approx(0.5)                                     # 200 contracts on one of two
    assert key_stats.book_depth(None, {}) is None
    assert key_stats.book_depth({"depth": 30, "markets": {}}, {}) is None     # an empty tape: nothing to measure


def test_key_stats_main_reads_the_other_outputs(study, capsys):
    study.history.write_snapshots()
    for name, module in (("findings.json", study.findings), ("strategies.json", study.strategies_backtest)):
        if not os.path.exists(name):
            module.main()
    capsys.readouterr()
    study.key_stats.main()
    with open("key_stats.json", encoding="utf-8") as fh:
        k = json.load(fh)
    assert k["markets"] == len(study.analyze.load_rows())
    assert (k["from"], k["split"], k["to"]) == ("2025-12-10", "2026-08-24", "2026-10-01")
    assert [r["scenario"] for r in k["kelly"]] == ["backtest", "realistic", "stress"]
    assert {e["base"] for e in k["exits"]} == {"$10 a bet", "3% a bet, 20% a window · $100"}
    assert k["realFills"] is None                     # the synthetic history has no liquidity.json: no real-fills account
    assert k["bookDepth"] is None                     # ... and no book to measure
    assert "one-bet Kelly" in capsys.readouterr().out
