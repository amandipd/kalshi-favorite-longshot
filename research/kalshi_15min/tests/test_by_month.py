"""by_month.py: the minute-8 favourites rule, plain and as the live bot trades it, by part of the history and by month.

`stats()` is checked on bets whose numbers can be worked out by hand, `bets()` against the rules it applies, and
`main()` end to end on the synthetic history, which has markets before Jul 18 in January and July.
"""

from __future__ import annotations

import json
import math

import pytest

T0 = 1_784_332_800  # 2026-07-18T00:00:00Z


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def bet(t, won, price=0.954, spread=0.01, series="KXBTC15M"):
    c = 10 / price
    f = fee(c, price)
    return {"t": t, "series": series, "won": won, "cost": price + f / c, "pnl": (c if won else 0.0) - 10 - f,
            "spread": spread, "live": True}


def test_stats_by_hand(study):
    bm = study.by_month
    assert bm.stats([]) is None
    bs = [bet(T0, True), bet(T0, False), bet(T0 + 900, True), bet(T0 + 900, True, spread=0.03)]
    s = bm.stats(bs)
    c = 10 / 0.954
    win, loss = c - 10 - fee(c, 0.954), -10 - fee(c, 0.954)
    cost = 0.954 + fee(c, 0.954) / c
    assert (s["bets"], s["windows"], s["won"]) == (4, 2, 0.75)
    assert s["cost"] == pytest.approx(cost, abs=1e-5) and s["kelly"] == pytest.approx((0.75 - cost) / (1 - cost), abs=1e-4)
    assert s["perBet"] == pytest.approx((3 * win + loss) / 4 * 100, abs=0.01)
    assert s["pnl"] == round(3 * win + loss, 2) and s["spread"] == pytest.approx(0.015)
    assert s["lo"] < s["perBet"] < s["hi"]


def test_one_window_has_no_range(study):
    s = study.by_month.stats([bet(T0, True), bet(T0, False)])
    assert s["lo"] is None and s["hi"] is None


def test_bets_are_the_minute_8_favourites_at_90c_and_up_in_the_edge_groups(study):
    bm, sb = study.by_month, study.strategies_backtest
    bs = bm.bets()
    windows, _, _ = sb.load()
    by_ticker = {m["ticker"]: (t, m) for t, ms in windows.items() for m in ms}
    assert bs and any(b["t"] < sb.ts(study.history.JUL18) for b in bs)
    live = sb.LIVE[0]
    for b in bs[:400]:
        t, m = next((t, m) for t, m in by_ticker.values() if t == b["t"] and m["series"] == b["series"])
        side, top = sb.favourite(*m["q"][8])
        assert m["group"] in sb.EDGE_GROUPS and sb.LO <= top <= sb.HI
        price = min(top + bm.SLIP, 0.999)
        assert b["cost"] == pytest.approx(price + fee(10 / price, price) / (10 / price))
        blackout = any(t < z and t + 900 > a for a, z in live["blackouts"])
        assert b["won"] == ((side == "yes") == m["yes"]) and b["live"] == (not blackout and not sb.skipped(live, m, side))


def test_the_live_rule_skips_the_fed_windows(study, monkeypatch):
    bm, sb = study.by_month, study.strategies_backtest
    first = min(b["t"] for b in bm.bets())
    monkeypatch.setattr(sb, "LIVE", [dict(sb.LIVE[0], blackouts=[(first, first + 900)])] + sb.LIVE[1:])
    assert not any(b["live"] for b in bm.bets() if b["t"] == first)


@pytest.fixture(scope="module")
def by_month(study):
    study.by_month.main()
    with open("by_month.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_main_writes_both_rules_by_part_and_month(study, by_month):
    assert [p["key"] for p in by_month["parts"]] == ["pre", "before", "after"]
    for rule in ("plain", "live"):
        t = by_month[rule]
        assert sum(s["bets"] for s in t["parts"].values()) == t["all"]["bets"]
        assert sum(s["bets"] for s in t["months"].values()) == t["all"]["bets"]
        assert sum(s["bets"] for s in t["preBySeries"].values()) == t["parts"]["pre"]["bets"]
        assert set(t["preBySeries"]) == {"KXBTC15M", "KXETH15M"}, "crypto only before Jul 18"
        assert "2026-01" in t["months"] and "2026-07" in t["months"]
    assert by_month["live"]["all"]["bets"] < by_month["plain"]["all"]["bets"], "the live rule skips the warning signs"


def test_main_prints_both_rules(study, capsys):
    study.by_month.main()
    out = capsys.readouterr().out
    assert "THE PLAIN RULE" in out and "THE LIVE BOT'S RULE" in out and "by month" in out and "by_month.json" in out


def test_a_part_with_no_bets_says_so(study, capsys):
    bm = study.by_month
    empty = {"all": None, "parts": {k: None for k, *_ in bm.PARTS}, "months": {"2026-01": None}, "preBySeries": {}}
    bm.show("NOTHING", empty)
    out = capsys.readouterr().out
    assert out.count("no bets") == 2 + len(bm.PARTS)
